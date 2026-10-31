cmake_minimum_required(VERSION 3.24)
project(GuanhengQmtReadOnlyFixed LANGUAGES C CXX)

# 固定上游与自有候选分别由原 native.py 快照；禁止从当前工作树取公共头。
foreach(root GH_FIXED_UPSTREAM_ROOT GH_FIXED_OWN_ROOT)
  if(NOT IS_ABSOLUTE "${${root}}" OR NOT EXISTS "${${root}}/input.json")
    message(FATAL_ERROR "${root} must identify a verified explicit source snapshot")
  endif()
endforeach()
if(NOT MSVC OR NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
  message(FATAL_ERROR "qmt-readonly-fixed requires MSVC x64")
endif()
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_MSVC_RUNTIME_LIBRARY MultiThreadedDLL)
set(CMAKE_POLICY_VERSION_MINIMUM 3.5)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(BUILD_SHARED_LIBS OFF CACHE BOOL "Static locked dependencies" FORCE)
set(BOOST_INCLUDE_LIBRARIES "filesystem;thread;asio;bind;circular_buffer;pool;interprocess;lockfree;algorithm;unordered;property_tree;xpressive" CACHE STRING "Required Boost components" FORCE)
set(BOOST_ENABLE_CMAKE ON CACHE BOOL "" FORCE)
set(BOOST_ENABLE_TESTING OFF CACHE BOOL "" FORCE)
set(SPDLOG_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(SPDLOG_BUILD_EXAMPLE OFF CACHE BOOL "" FORCE)
set(SPDLOG_INSTALL OFF CACHE BOOL "" FORCE)
foreach(dep boost spdlog rapidjson)
  if(NOT IS_DIRECTORY "${WT_DEPS_DIR}/${dep}")
    message(FATAL_ERROR "Missing locked source ${dep}; run scripts/native.py deps")
  endif()
endforeach()

# 嵌套的原 project() 重新载入编译器信息，因此在独立 wrapper 保存真实语言前缀。
file(WRITE "${CMAKE_BINARY_DIR}/wt-prefix-probe.h" "// include prefix probe\n")
file(WRITE "${CMAKE_BINARY_DIR}/wt-prefix-probe.cpp" "#include \"wt-prefix-probe.h\"\n")
execute_process(COMMAND "${CMAKE_CXX_COMPILER}" /nologo /showIncludes /E "${CMAKE_BINARY_DIR}/wt-prefix-probe.cpp"
  OUTPUT_VARIABLE prefix_out ERROR_VARIABLE prefix_err RESULT_VARIABLE prefix_result ENCODING AUTO TIMEOUT 15)
if(NOT prefix_result EQUAL 0)
  message(FATAL_ERROR "MSVC include prefix probe failed")
endif()
string(REGEX MATCH "([^\r\n]*: +)[A-Za-z]:[/\\][^\r\n]*wt-prefix-probe.h" prefix_match "${prefix_out}${prefix_err}")
if(NOT prefix_match)
  message(FATAL_ERROR "Could not identify localized MSVC include prefix")
endif()
set(WT_MSVC_INCLUDE_PREFIX "${CMAKE_MATCH_1}")
set(CMAKE_PROJECT_INCLUDE "${CMAKE_CURRENT_LIST_DIR}/msvc-includes.cmake")
include("${CMAKE_PROJECT_INCLUDE}")
add_compile_options(/utf-8 /EHsc /W3 /FIobjbase.h)
add_compile_definitions(NOMINMAX WIN32_LEAN_AND_MEAN _CRT_SECURE_NO_WARNINGS
  _SILENCE_STDEXT_HASH_DEPRECATION_WARNINGS BOOST_ALL_NO_LIB BOOST_BIND_GLOBAL_PLACEHOLDERS _WIN32_WINNT=0x0601)

add_subdirectory("${WT_DEPS_DIR}/boost" deps/boost EXCLUDE_FROM_ALL)
add_subdirectory("${WT_DEPS_DIR}/spdlog" deps/spdlog EXCLUDE_FROM_ALL)
add_library(nqp_host_dependencies INTERFACE)
target_include_directories(nqp_host_dependencies INTERFACE "${WT_DEPS_DIR}/rapidjson/include" "${WT_DEPS_DIR}/spdlog/include")
target_link_libraries(nqp_host_dependencies INTERFACE Boost::filesystem Boost::thread Boost::asio Boost::bind
  Boost::circular_buffer Boost::pool Boost::interprocess Boost::lockfree Boost::algorithm Boost::unordered
  Boost::property_tree Boost::xpressive spdlog::spdlog_header_only ws2_32 psapi dbghelp version user32 shell32 advapi32)

# 原 CMake 原样编译传递库；历史 original-build/.lib 不属于本工程搜索路径。
set(PLATFORM x64)
set(INCS "${WT_DEPS_DIR}/rapidjson/include" "${WT_DEPS_DIR}/spdlog/include")
foreach(component WTSUtils WTSTools)
  add_subdirectory("${GH_FIXED_UPSTREAM_ROOT}/src/${component}" "upstream/${component}")
  target_link_libraries(${component} nqp_host_dependencies)
  set_target_properties(${component} PROPERTIES ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib")
endforeach()
target_link_libraries(WTSTools WTSUtils)

set(production_sources
  "${GH_FIXED_OWN_ROOT}/src/GuanhengQmtBootstrap/ReadOnlyTrader.cpp"
  "${GH_FIXED_OWN_ROOT}/src/GuanhengQmtBootstrap/HttpMapping.cpp"
  "${GH_FIXED_OWN_ROOT}/src/GuanhengQmtBootstrap/AccountMapping.cpp"
  "${GH_FIXED_OWN_ROOT}/src/GuanhengQmtBootstrap/ShmAccountMapping.cpp"
  "${GH_FIXED_OWN_ROOT}/src/GuanhengCommon/QmtBoundReadCore.cpp"
  # Core和账户映射共用唯一Host codec，两个普通/排空插件均须链接实现。
  "${GH_FIXED_OWN_ROOT}/src/GuanhengCommon/QmtHostCodec.cpp"
  "${GH_FIXED_OWN_ROOT}/src/GuanhengCommon/QmtHostAccountClient.cpp"
  "${GH_FIXED_OWN_ROOT}/src/GuanhengCommon/QmtHostHistoryClient.cpp"
  "${GH_FIXED_OWN_ROOT}/src/GuanhengCommon/QmtHostReadClient.cpp"
  "${GH_FIXED_OWN_ROOT}/src/GuanhengCommon/BoundedSignedHttp.cpp"
  "${GH_FIXED_OWN_ROOT}/src/GuanhengCommon/QmtReadTransport.cpp"
  "${GH_FIXED_OWN_ROOT}/src/TraderQMTReadOnly/Factory.cpp")
foreach(target NqpTraderReadOnly NqpTraderReadOnlyDrain)
  add_library(${target} SHARED ${production_sources})
  target_include_directories(${target} PRIVATE "${GH_FIXED_OWN_ROOT}/src" "${GH_FIXED_UPSTREAM_ROOT}/src" "${WT_DEPS_DIR}/rapidjson/include")
  target_compile_definitions(${target} PRIVATE NQB_BUILD_DLL)
  # 原 WTSObject/ObjectPool 公开头需要 Boost 头闭包；这两个 target 只传播头。
  target_link_libraries(${target} PRIVATE Boost::smart_ptr Boost::pool winhttp bcrypt)
  set_target_properties(${target} PROPERTIES OUTPUT_NAME TraderQMTReadOnly ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib/${target}")
endforeach()
target_compile_definitions(NqpTraderReadOnlyDrain PRIVATE GH_QMT_HTTP_DRAIN_TESTING)
set_target_properties(NqpTraderReadOnly PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin/traders")
# 原 Adapter 从 CWD/traders 查找插件；门控测试拥有独立 CWD 与同名 DLL。
set_target_properties(NqpTraderReadOnlyDrain PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin/drain/traders")

set(adapter_sources)
foreach(source TraderAdapter WtHelper ActionPolicyMgr EventNotifier)
  list(APPEND adapter_sources "${GH_FIXED_UPSTREAM_ROOT}/src/WtCore/${source}.cpp")
endforeach()
add_library(NqpAdapterHost OBJECT ${adapter_sources})
target_include_directories(NqpAdapterHost PRIVATE "${GH_FIXED_UPSTREAM_ROOT}/src")
target_link_libraries(NqpAdapterHost PRIVATE WTSTools WTSUtils nqp_host_dependencies)
foreach(pair "NqpFixtureProbe|qmt_readonly_bootstrap/probe.cpp" "NqpHttpProbe|qmt_http_bootstrap/probe.cpp" "NqpNoConnectProbe|qmt_http_bootstrap/no_connect.cpp")
  string(REPLACE "|" ";" pair "${pair}")
  list(GET pair 0 target)
  list(GET pair 1 source)
  add_executable(${target} "${GH_FIXED_OWN_ROOT}/tests/integration/${source}" $<TARGET_OBJECTS:NqpAdapterHost>)
  target_include_directories(${target} PRIVATE "${GH_FIXED_OWN_ROOT}/src" "${GH_FIXED_UPSTREAM_ROOT}/src")
  target_link_libraries(${target} PRIVATE WTSTools WTSUtils nqp_host_dependencies winhttp bcrypt)
  set_target_properties(${target} PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
endforeach()

add_executable(NqpCngProbe "${GH_FIXED_OWN_ROOT}/tests/integration/qmt_http_bootstrap/cng_lifetime.cpp")
target_include_directories(NqpCngProbe PRIVATE "${GH_FIXED_OWN_ROOT}/src" "${GH_FIXED_UPSTREAM_ROOT}/src" "${WT_DEPS_DIR}/rapidjson/include")
target_link_libraries(NqpCngProbe PRIVATE WTSTools WTSUtils nqp_host_dependencies winhttp bcrypt)
set_target_properties(NqpCngProbe PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")

include(CTest)
find_package(Python3 3.10 REQUIRED COMPONENTS Interpreter)
# 参数化回归由原测试 owner 接线；所有测试均显式使用普通/门控目标路径。
include("${CMAKE_CURRENT_LIST_DIR}/tests.cmake")

install(TARGETS NqpTraderReadOnly RUNTIME DESTINATION app/traders)
install(TARGETS NqpFixtureProbe NqpHttpProbe NqpNoConnectProbe RUNTIME DESTINATION validation/bin)
install(FILES "${GH_FIXED_UPSTREAM_ROOT}/input.json" DESTINATION provenance RENAME upstream-input.json)
install(FILES "${GH_FIXED_OWN_ROOT}/input.json" DESTINATION provenance RENAME owned-input.json)
install(FILES "${GH_FIXED_UPSTREAM_ROOT}/LICENSE" DESTINATION licenses RENAME WonderTrader-MIT.txt)
install(FILES "${CMAKE_CURRENT_LIST_DIR}/readonly.example.json" DESTINATION examples)
# Install the portable validation closure explicitly. Historical compiler and
# missing-field diagnosis entry points stay in the repository, outside the ZIP.
foreach(name run invocation fixed_checks repair_regressions supplemental)
  install(FILES "${GH_FIXED_OWN_ROOT}/tests/integration/qmt_readonly_bootstrap/${name}.py" DESTINATION validation/tests/integration/qmt_readonly_bootstrap)
endforeach()
foreach(name run native_oracle abi no_connect)
  install(FILES "${GH_FIXED_OWN_ROOT}/tests/integration/qmt_http_bootstrap/${name}.py" DESTINATION validation/tests/integration/qmt_http_bootstrap)
endforeach()
install(FILES "${GH_FIXED_OWN_ROOT}/tests/integration/http/test_qmt_http.py" DESTINATION validation/tests/integration/http)
install(FILES "${GH_FIXED_OWN_ROOT}/scripts/native_support/__init__.py" "${GH_FIXED_OWN_ROOT}/scripts/native_support/artifact.py" "${GH_FIXED_OWN_ROOT}/scripts/native_support/qmt_readonly_fixed.py" DESTINATION validation/scripts/native_support)
set(CMAKE_INSTALL_SYSTEM_RUNTIME_DESTINATION app)
set(CMAKE_INSTALL_UCRT_LIBRARIES TRUE)
include(InstallRequiredSystemLibraries)
