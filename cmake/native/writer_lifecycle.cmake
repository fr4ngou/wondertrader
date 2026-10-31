# WLC：此目录来自固定原版加唯一批准覆盖，禁止指向共享工作树的冻结差异。
if(NOT IS_ABSOLUTE "${GH_WRITER_LIFECYCLE_SOURCE_ROOT}" OR
   NOT EXISTS "${GH_WRITER_LIFECYCLE_SOURCE_ROOT}/WtDataStorage/WtDataWriter.cpp")
  message(FATAL_ERROR "Writer lifecycle requires a prepared approved source directory")
endif()
set(_wlc "${GH_WRITER_LIFECYCLE_SOURCE_ROOT}/WtDataStorage")
add_library(WtDataStorageLifecycle SHARED
  "${_wlc}/WtDataWriter.cpp" "${_wlc}/WtDataReader.cpp"
  "${_wlc}/WtBtDtReader.cpp" "${_wlc}/WtRdmDtReader.cpp")
target_link_libraries(WtDataStorageLifecycle PRIVATE WTSUtils wt_native_dependencies)
set_target_properties(WtDataStorageLifecycle PROPERTIES
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
  LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
  ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib")
install(TARGETS WtDataStorageLifecycle RUNTIME DESTINATION app LIBRARY DESTINATION app)
