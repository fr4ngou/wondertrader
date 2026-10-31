cmake_minimum_required(VERSION 3.24)
project(GuanhengExecutionProduct LANGUAGES C CXX)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(GH_STANDARD_CTA_HOST ON CACHE BOOL "" FORCE)
set(BUILD_TESTING OFF CACHE BOOL "" FORCE)
add_subdirectory("${GH_FIXED_OWN_ROOT}/cmake/native/qmt_standard_product" product)

# 由本次实际linker生成完整绝对输入，覆盖响应文件和对象的DEFAULTLIB指令。
# 此专用构建接线沿用原目标及行为，不修改共享产品清单或框架。
set(GH_EXECUTION_LINK_INPUTS "${CMAKE_BINARY_DIR}/link-inputs")
file(MAKE_DIRECTORY "${GH_EXECUTION_LINK_INPUTS}")
foreach(target GuanhengCtaHost GuanhengCtaRuntime GuanhengStandardTrader
               GuanhengOriginalExecutionFactory GuanhengManagedStrategy)
  target_link_options(${target} PRIVATE
    /VERBOSE:LIB
    "/LINKREPROFULLPATHRSP:${GH_EXECUTION_LINK_INPUTS}/${target}.rsp")
endforeach()
