# 自有报价 DLL 独立同批编译 Common，保持既有 Native/交易目标。
add_library(GuanhengShmQuotes SHARED
  "${WT_ROOT}/src/GuanhengRuntime/ShmQuotesBridge.cpp"
  "${WT_ROOT}/src/GuanhengData/QmtTickMapping.cpp"
  "${WT_ROOT}/src/GuanhengCommon/BoundedSignedHttp.cpp"
  "${WT_ROOT}/src/GuanhengCommon/QmtBoundReadCore.cpp"
  "${WT_ROOT}/src/GuanhengCommon/QmtHostAccountClient.cpp"
  "${WT_ROOT}/src/GuanhengCommon/QmtHostCodec.cpp"
  "${WT_ROOT}/src/GuanhengCommon/QmtHostHistoryClient.cpp"
  "${WT_ROOT}/src/GuanhengCommon/QmtHostReadClient.cpp"
  "${WT_ROOT}/src/GuanhengCommon/QmtHostTradeClient.cpp"
  "${WT_ROOT}/src/GuanhengCommon/QmtReadTransport.cpp")
target_link_libraries(GuanhengShmQuotes PRIVATE wt_native_dependencies)
if(MSVC)
  target_compile_options(GuanhengShmQuotes PRIVATE /FIobjbase.h)
  target_compile_definitions(GuanhengShmQuotes PRIVATE NOMINMAX WIN32_LEAN_AND_MEAN)
  target_link_libraries(GuanhengShmQuotes PRIVATE winhttp bcrypt ws2_32 advapi32 ole32 user32)
endif()
set_target_properties(GuanhengShmQuotes PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
install(TARGETS GuanhengShmQuotes RUNTIME DESTINATION app LIBRARY DESTINATION app)
