library(testthat)

# Function with a bug
buggy_subtract <- function(x, y) {
return(x + y)  # Bug: should be x - y
}

context("String operations")

test_that("subtraction should work but fails", {
    expect_equal(buggy_subtract(5, 2), 3)  # This will fail
})

test_that("another failing test", {
    expect_equal(buggy_subtract(10, 3), 7)  # This will also fail
})
