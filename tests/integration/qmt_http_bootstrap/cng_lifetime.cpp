// 仅隔离进程：实际CNG句柄+唯一backing allocation的无分配顺序观察。
#include <Windows.h>
#include <bcrypt.h>
#include <cstdlib>
#include <new>
#include <cstdio>
#include <cstring>
#include <string>

namespace {
struct Observation
{
    void* backing=nullptr;void* deferred=nullptr;BCRYPT_HASH_HANDLE hash=nullptr;
    unsigned mode=0,clock=0,created=0,destroyed=0,closed=0,deleted=0;
    unsigned create_order=0,destroy_order=0,close_order=0,delete_order=0;
    bool free_seen=false,early_free=false,deferred_free=false;
    NTSTATUS destroy_status=0,close_status=0;
} observed;
void deallocate(void* pointer) noexcept
{
    if(pointer&&pointer==observed.backing&&!observed.free_seen){
        observed.free_seen=true;++observed.deleted;observed.delete_order=++observed.clock;
        if(!observed.destroyed){
            // 原样错误先触发vector的delete。仅探针延后物理free，稳定报告次序且保护真实CNG清理。
            observed.early_free=true;observed.deferred=pointer;observed.deferred_free=true;return;
        }
    }
    std::free(pointer);
}
}
void* operator new(std::size_t size){if(void* p=std::malloc(size?size:1))return p;throw std::bad_alloc();}
void* operator new[](std::size_t size){if(void* p=std::malloc(size?size:1))return p;throw std::bad_alloc();}
void operator delete(void* p) noexcept {deallocate(p);}
void operator delete[](void* p) noexcept {deallocate(p);}
void operator delete(void* p,std::size_t) noexcept {deallocate(p);}
void operator delete[](void* p,std::size_t) noexcept {deallocate(p);}

NTSTATUS WINAPI tracked_create(BCRYPT_ALG_HANDLE algorithm,BCRYPT_HASH_HANDLE* hash,PUCHAR object,ULONG bytes,PUCHAR secret,ULONG secret_size,ULONG flags)
{
    auto status=::BCryptCreateHash(algorithm,hash,object,bytes,secret,secret_size,flags);
    if(status>=0){observed.backing=object;observed.hash=*hash;++observed.created;observed.create_order=++observed.clock;}
    return status;
}
NTSTATUS WINAPI tracked_data(BCRYPT_HASH_HANDLE hash,PUCHAR input,ULONG bytes,ULONG flags)
{
    if(observed.mode==1)return static_cast<NTSTATUS>(0xC0000001u);
    return ::BCryptHashData(hash,input,bytes,flags);
}
NTSTATUS WINAPI tracked_finish(BCRYPT_HASH_HANDLE hash,PUCHAR digest,ULONG bytes,ULONG flags)
{
    if(observed.mode==2)return static_cast<NTSTATUS>(0xC0000001u);
    return ::BCryptFinishHash(hash,digest,bytes,flags);
}
NTSTATUS WINAPI tracked_destroy(BCRYPT_HASH_HANDLE hash)
{
    observed.destroy_order=++observed.clock;
    observed.destroy_status=::BCryptDestroyHash(hash);
    ++observed.destroyed;
    if(observed.deferred){std::free(observed.deferred);observed.deferred=nullptr;}
    return observed.destroy_status;
}
NTSTATUS WINAPI tracked_close(BCRYPT_ALG_HANDLE algorithm,ULONG flags)
{
    observed.close_order=++observed.clock;observed.close_status=::BCryptCloseAlgorithmProvider(algorithm,flags);++observed.closed;return observed.close_status;
}

// 直接编译该快照的实际映射TU；包装只在本进程可见，普通/门控DLL保持系统CNG调用。
#define BCryptCreateHash tracked_create
#define BCryptHashData tracked_data
#define BCryptFinishHash tracked_finish
#define BCryptDestroyHash tracked_destroy
#define BCryptCloseAlgorithmProvider tracked_close
#include "GuanhengQmtBootstrap/AccountMapping.cpp"
#undef BCryptCreateHash
#undef BCryptHashData
#undef BCryptFinishHash
#undef BCryptDestroyHash
#undef BCryptCloseAlgorithmProvider

int main(int argc,char** argv)
{
    if(argc!=2)return 2;
    if(std::strcmp(argv[1],"hash-data-failure")==0)observed.mode=1;
    else if(std::strcmp(argv[1],"finish-failure")==0)observed.mode=2;
    else if(std::strcmp(argv[1],"success")!=0)return 2;
    bool threw=false;std::string value;
    try{value=guanheng::bootstrap::scoped_trade_id("SSE","600000",20261022,"00000031");}catch(const std::exception&){threw=true;}
    const bool vector_ok=observed.mode?threw:!threw&&value=="nqh1.kn5Re6ZjMKt7HL7_oIk1ErE3qY1uSxbvcPE_S5hSlzg";
    const bool lifetime_ok=observed.backing&&observed.hash&&observed.created==1&&observed.destroyed==1&&observed.closed==1&&observed.deleted==1&&!observed.early_free&&observed.destroy_status>=0&&observed.close_status>=0&&observed.create_order<observed.destroy_order&&observed.destroy_order<observed.delete_order&&observed.destroy_order<observed.close_order;
    std::printf("{\"created\":%u,\"destroyed\":%u,\"closed\":%u,\"backing_deleted\":%u,\"create_order\":%u,\"destroy_order\":%u,\"close_order\":%u,\"delete_order\":%u,\"early_backing_release\":%s,\"test_deferred_physical_free\":%s,\"exception\":%s,\"fixed_vector_or_expected_failure\":%s,\"lifetime_ok\":%s}\n",observed.created,observed.destroyed,observed.closed,observed.deleted,observed.create_order,observed.destroy_order,observed.close_order,observed.delete_order,observed.early_free?"true":"false",observed.deferred_free?"true":"false",threw?"true":"false",vector_ok?"true":"false",lifetime_ok?"true":"false");
    return lifetime_ok&&vector_ok?0:1;
}
