if(BUILD_TESTING)
  if(NOT EXISTS "${GH_FIXED_QMT_ROOT}/input.json")
    message(FATAL_ERROR "CTest requires the explicit controlled fixed QMT fixture")
  endif()
  foreach(kind fixture regression supplemental http drain abi no-connect cng)
    add_test(NAME nqp-${kind} COMMAND "${Python3_EXECUTABLE}" -B
      "${GH_FIXED_OWN_ROOT}/tests/integration/qmt_readonly_bootstrap/fixed_checks.py"
      --kind "${kind}" --owned-root "${GH_FIXED_OWN_ROOT}" --bin-root "${CMAKE_BINARY_DIR}/bin"
      --qmt-fixture "${GH_FIXED_QMT_ROOT}" --work "${CMAKE_BINARY_DIR}/validation")
    set_tests_properties(nqp-${kind} PROPERTIES TIMEOUT 420)
  endforeach()
  set_tests_properties(nqp-supplemental PROPERTIES DEPENDS nqp-fixture)
endif()
