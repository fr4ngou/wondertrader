"""证券目录搜索HTTP入口。"""

from fastapi import APIRouter, HTTPException, Query, Request

from .contracts.security_catalog import SecuritySearchResponse
from .security_catalog import SecurityCatalog, SecurityCatalogError


def router(catalog: SecurityCatalog) -> APIRouter:
    result = APIRouter()

    @result.get("/v1/ui/securities/search", response_model=SecuritySearchResponse)
    async def search(request: Request, query: str = Query(min_length=1, max_length=64),
                     limit: int = Query(default=12, ge=1, le=30)):
        if request.headers.get("content-length", "0") != "0" or request.headers.get("transfer-encoding"):
            raise HTTPException(422, "证券搜索不接受请求体")
        try:
            matches = catalog.search(query, limit)
        except SecurityCatalogError as error:
            if not catalog.available:
                raise HTTPException(503, str(error)) from None
            raise HTTPException(422, str(error)) from None
        return SecuritySearchResponse(query=query.strip(), catalog_id=catalog.catalog_id,
                                      generated_at=catalog.generated_at, results=matches)

    return result
