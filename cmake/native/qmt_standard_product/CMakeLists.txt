cmake_minimum_required(VERSION 3.24)
project(GuanhengQmtStandardProduct LANGUAGES C CXX)

foreach(root GH_FIXED_UPSTREAM_ROOT GH_FIXED_OWN_ROOT)
  if(NOT IS_ABSOLUTE "${${root}}" OR NOT EXISTS "${${root}}/input.json")
    message(FATAL_ERROR "${root} must identify a verified explicit source snapshot")
  endif()
  # Windows调用者可传原生反斜杠路径；安装脚本需要统一的CMake路径表示。
  file(TO_CMAKE_PATH "${${root}}" normalized_root)
  set(${root} "${normalized_root}")
endforeach()
if(NOT MSVC OR NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
  message(FATAL_ERROR "qmt-standard-product requires MSVC x64")
endif()

# 沿既有固定来源/锁定依赖工程准入；排除其默认构建，正式目标只链接正常依赖。
# 原工程仍会配置其验证入口，因此configure沿用原Python解释器依赖；不运行测试。
option(BUILD_TESTING "Configure inherited validation entries" OFF)
add_subdirectory("${GH_FIXED_OWN_ROOT}/cmake/native/qmt_readonly_fixed" readonly-support EXCLUDE_FROM_ALL)
# 取回原工程实际探测的本机showIncludes前缀，供本目录正常插件的Ninja依赖扫描使用。
get_directory_property(WT_MSVC_INCLUDE_PREFIX
  DIRECTORY "${GH_FIXED_OWN_ROOT}/cmake/native/qmt_readonly_fixed" DEFINITION WT_MSVC_INCLUDE_PREFIX)
include("${GH_FIXED_OWN_ROOT}/cmake/native/qmt_readonly_fixed/msvc-includes.cmake")
include("${GH_FIXED_OWN_ROOT}/src/TraderQMT/StandardTargets.cmake")
guanheng_add_standard_trader(GuanhengStandardTrader TraderQMTStandard)

# 策略宿主链接此自有扩展；原WT执行器及Adapter从批准的上游快照取得。
add_library(GuanhengBrokerQueryContext STATIC
  "${GH_FIXED_OWN_ROOT}/src/GuanhengExecution/BrokerQueryContext.cpp"
  "${GH_FIXED_OWN_ROOT}/src/GuanhengExecution/OwnerExecCommand.cpp"
  "${GH_FIXED_OWN_ROOT}/src/GuanhengExecution/StandardExecutionHost.cpp"
  "${GH_FIXED_OWN_ROOT}/src/GuanhengExecution/ExecutionEnvironment.cpp")
guanheng_configure_standard_target(GuanhengBrokerQueryContext)
set_target_properties(GuanhengBrokerQueryContext PROPERTIES ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib")

option(GH_STANDARD_CONTEXT_MAIN "Build the broker-query positive main-path driver" OFF)
option(GH_STANDARD_CTA "Build the native CTA execution library" OFF)
option(GH_STANDARD_CTA_MAIN "Build the public native CTA assembly main path" OFF)
option(GH_STANDARD_CTA_HOST "Build the installed managed CTA execution host" OFF)
if(GH_STANDARD_CTA_MAIN OR GH_STANDARD_CTA_HOST)
  set(GH_STANDARD_CTA ON)
endif()
if(GH_STANDARD_CONTEXT_MAIN OR GH_STANDARD_CTA_MAIN OR GH_STANDARD_CTA_HOST)
  # 此验证目标直接编译固定上游算法工厂，源码保持；正式发行另沿原工厂构建。
  add_library(GuanhengOriginalExecutionFactory SHARED)
  foreach(unit WtExeFact WtTWapExeUnit WtMinImpactExeUnit WtDiffMinImpactExeUnit WtStockMinImpactExeUnit WtVWapExeUnit WtStockVWapExeUnit WtOrdMon)
    target_sources(GuanhengOriginalExecutionFactory PRIVATE "${GH_FIXED_UPSTREAM_ROOT}/src/WtExeFact/${unit}.cpp")
  endforeach()
  guanheng_configure_standard_target(GuanhengOriginalExecutionFactory)
  set_target_properties(GuanhengOriginalExecutionFactory PROPERTIES OUTPUT_NAME WtExeFact
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin/executers")
  if(GH_STANDARD_CTA_HOST)
    install(TARGETS GuanhengOriginalExecutionFactory RUNTIME DESTINATION app/executers)
  endif()
endif()
if(GH_STANDARD_CTA_HOST)
  add_library(GuanhengManagedStrategy SHARED "${GH_FIXED_OWN_ROOT}/src/GuanhengRealtime/ManagedStrategyBridge.cpp")
  guanheng_configure_standard_target(GuanhengManagedStrategy)
  set_target_properties(GuanhengManagedStrategy PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin/strategies")
  install(TARGETS GuanhengManagedStrategy RUNTIME DESTINATION app/strategies)
  add_library(GuanhengCtaRuntime SHARED "${GH_FIXED_OWN_ROOT}/src/GuanhengExecution/CtaProcess.cpp")
  guanheng_configure_standard_target(GuanhengCtaRuntime)
  target_compile_definitions(GuanhengCtaRuntime PRIVATE GH_CTA_RUNTIME_BUILD=1)
  target_link_libraries(GuanhengCtaRuntime PRIVATE GuanhengCtaExecution GuanhengBrokerQueryContext WtCore)
  set_target_properties(GuanhengCtaRuntime PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
  add_executable(GuanhengCtaHost "${GH_FIXED_OWN_ROOT}/src/GuanhengExecution/main.cpp")
  guanheng_configure_standard_target(GuanhengCtaHost)
  target_link_libraries(GuanhengCtaHost PRIVATE GuanhengCtaRuntime)
  set_target_properties(GuanhengCtaHost PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
  add_dependencies(GuanhengCtaHost GuanhengStandardTrader GuanhengOriginalExecutionFactory GuanhengManagedStrategy)
  install(TARGETS GuanhengCtaHost GuanhengCtaRuntime RUNTIME DESTINATION app ARCHIVE DESTINATION lib)
  install(FILES "${GH_FIXED_OWN_ROOT}/src/GuanhengExecution/CtaProcess.h" DESTINATION include/GuanhengExecution)
  install(FILES "${GH_FIXED_OWN_ROOT}/src/GuanhengRealtime/ManagedStrategyBridge.h"
    "${GH_FIXED_OWN_ROOT}/src/GuanhengRealtime/RealtimeBridge.h" DESTINATION include/GuanhengRealtime)
endif()
if(GH_STANDARD_CONTEXT_MAIN)
  add_executable(GuanhengBrokerContextMain
    "${GH_FIXED_OWN_ROOT}/tests/integration/qmt_broker_context/main_probe.cpp"
    "${GH_FIXED_UPSTREAM_ROOT}/src/WtCore/WtLocalExecuter.cpp"
    "${GH_FIXED_UPSTREAM_ROOT}/src/WtCore/WtExecuterFactory.cpp"
    "${GH_FIXED_UPSTREAM_ROOT}/src/WtCore/WtExecMgr.cpp"
    "${GH_FIXED_UPSTREAM_ROOT}/src/WtCore/WtFilterMgr.cpp"
    $<TARGET_OBJECTS:NqpAdapterHost>)
  guanheng_configure_standard_target(GuanhengBrokerContextMain)
  target_link_libraries(GuanhengBrokerContextMain PRIVATE GuanhengBrokerQueryContext)
  set_target_properties(GuanhengBrokerContextMain PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
  add_dependencies(GuanhengBrokerContextMain GuanhengStandardTrader GuanhengOriginalExecutionFactory)
  add_executable(GuanhengExecutionHostMain
    "${GH_FIXED_OWN_ROOT}/tests/integration/qmt_broker_context/product_host_probe.cpp"
    "${GH_FIXED_UPSTREAM_ROOT}/src/WtCore/WtLocalExecuter.cpp"
    "${GH_FIXED_UPSTREAM_ROOT}/src/WtCore/WtExecuterFactory.cpp"
    "${GH_FIXED_UPSTREAM_ROOT}/src/WtCore/WtExecMgr.cpp"
    "${GH_FIXED_UPSTREAM_ROOT}/src/WtCore/WtFilterMgr.cpp"
    $<TARGET_OBJECTS:NqpAdapterHost>)
  guanheng_configure_standard_target(GuanhengExecutionHostMain)
  target_link_libraries(GuanhengExecutionHostMain PRIVATE GuanhengBrokerQueryContext)
  set_target_properties(GuanhengExecutionHostMain PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
  add_dependencies(GuanhengExecutionHostMain GuanhengStandardTrader GuanhengOriginalExecutionFactory)
  add_executable(GuanhengExecutionOwnerMain
    "${GH_FIXED_OWN_ROOT}/tests/integration/qmt_broker_context/owner_bridge_probe.cpp"
    "${GH_FIXED_UPSTREAM_ROOT}/src/WtCore/WtExecMgr.cpp"
    "${GH_FIXED_UPSTREAM_ROOT}/src/WtCore/WtFilterMgr.cpp"
    $<TARGET_OBJECTS:NqpAdapterHost>)
  guanheng_configure_standard_target(GuanhengExecutionOwnerMain)
  target_link_libraries(GuanhengExecutionOwnerMain PRIVATE GuanhengBrokerQueryContext)
  set_target_properties(GuanhengExecutionOwnerMain PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
endif()

# 单独产品目录显式选择标准工厂，不改变旧Factory.cpp或旧插件的缺省含义。
install(FILES "${GH_FIXED_OWN_ROOT}/src/GuanhengCommon/AccountAttributionProtocol.h" DESTINATION include/GuanhengCommon)
install(TARGETS GuanhengStandardTrader RUNTIME DESTINATION app/traders)
install(TARGETS GuanhengBrokerQueryContext ARCHIVE DESTINATION lib)
install(FILES "${GH_FIXED_OWN_ROOT}/src/GuanhengExecution/BrokerQueryContext.h"
  "${GH_FIXED_OWN_ROOT}/src/GuanhengExecution/OwnerExecCommand.h"
  "${GH_FIXED_OWN_ROOT}/src/GuanhengExecution/StandardExecutionHost.h"
  "${GH_FIXED_OWN_ROOT}/src/GuanhengExecution/ExecutionEnvironment.h"
  "${GH_FIXED_OWN_ROOT}/src/GuanhengExecution/QueryFirstSubmission.h" DESTINATION include/GuanhengExecution)
install(FILES "${GH_FIXED_OWN_ROOT}/src/TraderQMT/StandardSubmission.h"
  "${GH_FIXED_OWN_ROOT}/src/TraderQMT/StandardQmtTrader.h" DESTINATION include/TraderQMT)
install(FILES "${GH_FIXED_UPSTREAM_ROOT}/input.json" DESTINATION provenance RENAME upstream-input.json)
install(FILES "${GH_FIXED_OWN_ROOT}/input.json" DESTINATION provenance RENAME owned-input.json)

# 仅以实际安装目录和原SDK公共头编译消费端，防止源码include掩盖漏装头文件。
if(DEFINED GH_STANDARD_INSTALLED_INCLUDE_ROOT)
  if(NOT IS_ABSOLUTE "${GH_STANDARD_INSTALLED_INCLUDE_ROOT}" OR NOT EXISTS "${GH_STANDARD_INSTALLED_INCLUDE_ROOT}/GuanhengExecution/StandardExecutionHost.h")
    message(FATAL_ERROR "GH_STANDARD_INSTALLED_INCLUDE_ROOT must identify an actual installation")
  endif()
  add_library(GuanhengInstalledHostHeaders OBJECT "${GH_FIXED_OWN_ROOT}/tests/integration/qmt_broker_context/installed_host_header_probe.cpp")
  target_include_directories(GuanhengInstalledHostHeaders PRIVATE "${GH_STANDARD_INSTALLED_INCLUDE_ROOT}" "${GH_FIXED_UPSTREAM_ROOT}/src")
  target_link_libraries(GuanhengInstalledHostHeaders PRIVATE nqp_host_dependencies)
  target_compile_features(GuanhengInstalledHostHeaders PRIVATE cxx_std_17)
  target_compile_options(GuanhengInstalledHostHeaders PRIVATE /utf-8 /EHsc /W3 /FIobjbase.h)
  target_compile_definitions(GuanhengInstalledHostHeaders PRIVATE NOMINMAX WIN32_LEAN_AND_MEAN _CRT_SECURE_NO_WARNINGS _SILENCE_STDEXT_HASH_DEPRECATION_WARNINGS BOOST_ALL_NO_LIB BOOST_BIND_GLOBAL_PLACEHOLDERS _WIN32_WINNT=0x0601)
  set_target_properties(GuanhengInstalledHostHeaders PROPERTIES MSVC_RUNTIME_LIBRARY MultiThreadedDLL)
endif()

if(GH_STANDARD_CTA)
  # 固定上游仍声明旧CMake最低版本；沿已有原生构建的调用方兼容政策，不改上游文件。
  set(CMAKE_POLICY_VERSION_MINIMUM 3.5)
  set(PLATFORM x64)
  set(INCS "${WT_DEPS_DIR}/rapidjson/include" "${WT_DEPS_DIR}/spdlog/include")
  add_subdirectory("${GH_FIXED_UPSTREAM_ROOT}/src/WtCore" original-cta-core EXCLUDE_FROM_ALL)
  # 与既验CTA工程相同，先装入Windows系统头，再编译原WT头，保持其源码字节。
  target_compile_options(WtCore PRIVATE /utf-8 /EHsc /W3 /FIobjbase.h)
  target_compile_definitions(WtCore PRIVATE NOMINMAX WIN32_LEAN_AND_MEAN _CRT_SECURE_NO_WARNINGS _SILENCE_STDEXT_HASH_DEPRECATION_WARNINGS)
  set_target_properties(WtCore PROPERTIES MSVC_RUNTIME_LIBRARY MultiThreadedDLL)
  target_link_libraries(WtCore WTSTools WTSUtils nqp_host_dependencies)
  add_library(GuanhengCtaExecution STATIC "${GH_FIXED_OWN_ROOT}/src/GuanhengExecution/CtaExecutionSession.cpp")
  guanheng_configure_standard_target(GuanhengCtaExecution)
  target_link_libraries(GuanhengCtaExecution PRIVATE GuanhengBrokerQueryContext WtCore)
  set_target_properties(GuanhengCtaExecution PROPERTIES ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib")
  install(TARGETS GuanhengCtaExecution ARCHIVE DESTINATION lib)
  install(FILES "${GH_FIXED_OWN_ROOT}/src/GuanhengExecution/CtaExecutionSession.h" DESTINATION include/GuanhengExecution)
  if(TARGET GuanhengInstalledHostHeaders)
    target_compile_definitions(GuanhengInstalledHostHeaders PRIVATE GH_INSTALLED_CTA=1)
  endif()
endif()
if(GH_STANDARD_CTA_MAIN)
  add_library(ParserGuanhengCtaSynthetic SHARED "${GH_FIXED_OWN_ROOT}/tests/integration/qmt_cta_execution/synthetic_parser.cpp")
  guanheng_configure_standard_target(ParserGuanhengCtaSynthetic)
  set_target_properties(ParserGuanhengCtaSynthetic PROPERTIES OUTPUT_NAME ParserGuanhengSynthetic RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin/parsers")
  add_library(ReaderGuanhengCtaSynthetic SHARED "${GH_FIXED_OWN_ROOT}/tests/integration/qmt_cta_execution/synthetic_reader.cpp")
  guanheng_configure_standard_target(ReaderGuanhengCtaSynthetic)
  set_target_properties(ReaderGuanhengCtaSynthetic PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
  add_executable(GuanhengCtaExecutionMain "${GH_FIXED_OWN_ROOT}/tests/integration/qmt_cta_execution/cta_main_probe.cpp")
  guanheng_configure_standard_target(GuanhengCtaExecutionMain)
  target_link_libraries(GuanhengCtaExecutionMain PRIVATE GuanhengCtaExecution GuanhengBrokerQueryContext WtCore)
  set_target_properties(GuanhengCtaExecutionMain PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
  add_dependencies(GuanhengCtaExecutionMain GuanhengStandardTrader GuanhengOriginalExecutionFactory ParserGuanhengCtaSynthetic ReaderGuanhengCtaSynthetic)
endif()
