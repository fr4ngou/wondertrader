cmake_minimum_required(VERSION 3.24)
project(GuanhengNativeReader LANGUAGES C CXX)

# 固定上游与自有候选分别由原 native.py 快照；禁止从当前工作树取公共头。
foreach(root GH_FIXED_UPSTREAM_ROOT GH_FIXED_OWN_ROOT)
  if(NOT IS_ABSOLUTE "${${root}}" OR NOT EXISTS "${${root}}/input.json")
    message(FATAL_ERROR "${root} must identify a verified explicit source snapshot")
  endif()
endforeach()
if(NOT MSVC OR NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
  message(FATAL_ERROR "reader-product requires MSVC x64")
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
foreach(component WTSUtils WTSTools WtCore WtDataStorage WtDtHelper)
  add_subdirectory("${GH_FIXED_UPSTREAM_ROOT}/src/${component}" "upstream/${component}")
  target_link_libraries(${component} nqp_host_dependencies)
  set_target_properties(${component} PROPERTIES ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib" RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
endforeach()
target_link_libraries(WTSTools WTSUtils)


target_link_libraries(WtCore WTSTools WTSUtils)
target_link_libraries(WtDtHelper WTSTools WTSUtils)

# NRC is selected explicitly and has its own source tree and output directory.
# The baseline storage DLL remains independently available.
add_library(WtDataStorageNrc SHARED
  "${GH_NRC_ROOT}/src/WtDataStorage/WtDataWriter.cpp"
  "${GH_NRC_ROOT}/src/WtDataStorage/WtDataReader.cpp"
  "${GH_NRC_ROOT}/src/WtDataStorage/WtBtDtReader.cpp"
  "${GH_NRC_ROOT}/src/WtDataStorage/WtRdmDtReader.cpp")
target_link_libraries(WtDataStorageNrc PRIVATE WTSUtils nqp_host_dependencies)
set_target_properties(WtDataStorageNrc PROPERTIES OUTPUT_NAME WtDataStorage
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin/nrc"
  ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib/nrc")

add_library(GuanhengRealtimeReader SHARED
  "${GH_FIXED_OWN_ROOT}/src/ReaderGuanhengRealtime/Factory.cpp"
  "${GH_FIXED_OWN_ROOT}/src/GuanhengData/StrategyReader.cpp"
  "${GH_FIXED_OWN_ROOT}/src/GuanhengData/ReaderHttpClient.cpp"
  "${GH_EMBEDDED_READER_ROOT}/src/WtDataStorage/WtDataReader.cpp")
set_source_files_properties("${GH_EMBEDDED_READER_ROOT}/src/WtDataStorage/WtDataReader.cpp"
  PROPERTIES COMPILE_DEFINITIONS "createDataReader=gh_original_createDataReader;deleteDataReader=gh_original_deleteDataReader")
target_include_directories(GuanhengRealtimeReader PRIVATE "${GH_FIXED_UPSTREAM_ROOT}/src")
target_link_libraries(GuanhengRealtimeReader PRIVATE WTSTools WTSUtils nqp_host_dependencies winhttp bcrypt)
set_target_properties(GuanhengRealtimeReader PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
  ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib")

foreach(pair "GuanhengNativeMinuteProbe|native_minute_reader/probe.cpp"
    "GuanhengNativeMinuteBoundary|native_minute_reader/boundary.cpp"
    "GuanhengNativeMinuteHost|native_minute_reader/host.cpp"
    "GuanhengPublishedDailyProbe|native_daily_publication/probe.cpp")
  string(REPLACE "|" ";" pair "${pair}")
  list(GET pair 0 target)
  list(GET pair 1 source)
  add_executable(${target} "${GH_FIXED_OWN_ROOT}/tests/integration/${source}")
  target_include_directories(${target} PRIVATE "${GH_FIXED_UPSTREAM_ROOT}/src")
  target_link_libraries(${target} PRIVATE WtCore WTSTools WTSUtils nqp_host_dependencies winhttp bcrypt)
  set_target_properties(${target} PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
endforeach()

if(GH_BUILD_WRITER_LIFECYCLE)
  add_library(wt_native_dependencies ALIAS nqp_host_dependencies)
  include("${GH_FIXED_OWN_ROOT}/cmake/native/writer_lifecycle.cmake")
endif()
if(GH_BUILD_DATA_COMPONENTS)
  if(NOT GH_BUILD_WRITER_LIFECYCLE)
    message(FATAL_ERROR "data components require the explicit approved lifecycle variant")
  endif()
  include("${CMAKE_CURRENT_LIST_DIR}/data_components.cmake")
endif()
install(TARGETS GuanhengRealtimeReader WtDataStorage WtDtHelper RUNTIME DESTINATION app)
install(TARGETS WtDataStorageNrc RUNTIME DESTINATION app/nrc)
install(TARGETS GuanhengNativeMinuteProbe GuanhengNativeMinuteBoundary GuanhengNativeMinuteHost
  GuanhengPublishedDailyProbe RUNTIME DESTINATION validation/bin)
install(FILES "${GH_FIXED_UPSTREAM_ROOT}/LICENSE" DESTINATION licenses RENAME WonderTrader-MIT.txt)
set(CMAKE_INSTALL_SYSTEM_RUNTIME_DESTINATION app)
set(CMAKE_INSTALL_UCRT_LIBRARIES TRUE)
include(InstallRequiredSystemLibraries)
