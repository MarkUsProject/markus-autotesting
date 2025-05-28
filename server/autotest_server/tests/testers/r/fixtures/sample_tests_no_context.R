library(testthat)

# Function to test
multiply_two <- function(x) {
return(x * 2)
}

# Test without context (no context() call)
test_that("multiplication works", {
    expect_equal(multiply_two(2), 4)
expect_equal(multiply_two(5), 10)
})
