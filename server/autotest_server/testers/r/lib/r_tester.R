library(testthat)
library(rjson)
args <- commandArgs(TRUE)
test_results <- test_file(args[1], reporter = ListReporter)
for (i in 1:length(test_results)) {
  for (j in 1:length(test_results[[i]]$results)) {
    result <- test_results[[i]]$results[[j]]
    expectation <- class(result)[1]
    test_results[[i]]$results[[j]]$type <- expectation
  }
}
json <- toJSON(test_results)
cat(json)
