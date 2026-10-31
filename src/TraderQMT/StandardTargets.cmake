include_guard(GLOBAL)

# 调用方提供已核定的upstream/owned快照及qmt_readonly_fixed依赖目标；
# 清单仅含正常Standard实现，测试工程可复用清单后另建自己的注入目标。
function(guanheng_standard_sources common_output standard_output)
  set(common_sources)
  foreach(name BoundedSignedHttp QmtReadTransport QmtHostReadClient QmtHostCodec
      QmtHostTradeClient QmtBoundReadCore QmtHostHistoryClient QmtHostAccountClient)
    list(APPEND common_sources "${GH_FIXED_OWN_ROOT}/src/GuanhengCommon/${name}.cpp")
  endforeach()
  set(standard_sources ${common_sources}
    "${GH_FIXED_OWN_ROOT}/src/GuanhengQmtBootstrap/AccountMapping.cpp"
    "${GH_FIXED_OWN_ROOT}/src/GuanhengQmtBootstrap/ShmAccountMapping.cpp"
    "${GH_FIXED_OWN_ROOT}/src/GuanhengQmtBootstrap/AccountEventMatch.cpp"
    "${GH_FIXED_OWN_ROOT}/src/GuanhengQmtBootstrap/QmtAccountIdentity.cpp"
    "${GH_FIXED_OWN_ROOT}/src/TraderQMT/EventDeliveryIndex.cpp"
    "${GH_FIXED_OWN_ROOT}/src/TraderQMT/StandardQmtTrader.cpp"
    "${GH_FIXED_OWN_ROOT}/src/TraderQMT/StandardFactory.cpp")
  set(${common_output} "${common_sources}" PARENT_SCOPE)
  set(${standard_output} "${standard_sources}" PARENT_SCOPE)
endfunction()

# 正常插件和使用同一源码的宿主共用编译环境；不隐式启用任何测试宏。
function(guanheng_configure_standard_target target)
  foreach(dependency WTSTools WTSUtils nqp_host_dependencies)
    if(NOT TARGET ${dependency})
      message(FATAL_ERROR "Missing fixed dependency target: ${dependency}")
    endif()
  endforeach()
  target_include_directories(${target} PRIVATE "${GH_FIXED_OWN_ROOT}/src" "${GH_FIXED_UPSTREAM_ROOT}/src")
  target_compile_features(${target} PRIVATE cxx_std_17)
  target_compile_options(${target} PRIVATE /utf-8 /EHsc /W3 /FIobjbase.h)
  target_compile_definitions(${target} PRIVATE NOMINMAX WIN32_LEAN_AND_MEAN
    _CRT_SECURE_NO_WARNINGS _SILENCE_STDEXT_HASH_DEPRECATION_WARNINGS
    BOOST_ALL_NO_LIB BOOST_BIND_GLOBAL_PLACEHOLDERS _WIN32_WINNT=0x0601)
  set_target_properties(${target} PROPERTIES MSVC_RUNTIME_LIBRARY MultiThreadedDLL)
  target_link_libraries(${target} PRIVATE WTSTools WTSUtils nqp_host_dependencies winhttp bcrypt)
endfunction()

function(guanheng_add_standard_trader target output_name)
  guanheng_standard_sources(common_sources standard_sources)
  add_library(${target} SHARED ${standard_sources})
  guanheng_configure_standard_target(${target})
  target_compile_definitions(${target} PRIVATE GH_QMT_STANDARD_BUILD_DLL)
  set_target_properties(${target} PROPERTIES OUTPUT_NAME "${output_name}"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin/traders"
    ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib/${target}")
endfunction()
