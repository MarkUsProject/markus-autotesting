library(testthat)

# Function to test
add_one <- function(x) {
return(x + 1)
}

# Test with context
context("Basic arithmetic")

test_that("addition works correctly", {
    expect_equal(add_one(1), 2)
expect_equal(add_one(0), 1)
})

test_that("negative numbers work", {
    expect_equal(add_one(-1), 0)
}) 