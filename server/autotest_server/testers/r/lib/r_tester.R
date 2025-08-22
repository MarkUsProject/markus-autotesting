sink(file="/dev/null")
library(testthat)
library(rjson)
args <- commandArgs(TRUE)
test_results <- testthat::test_file(args[1], reporter = testthat::ListReporter)
annotations <- list()
tags <- list()
overall_comments <- list()

for (i in 1:length(test_results)) {
  for (j in 1:length(test_results[[i]]$results)) {
    result <- test_results[[i]]$results[[j]]
    expectation <- class(result)[1]
    test_results[[i]]$results[[j]]$type <- expectation

    # If the test raised an error, the $trace attribute of the test result is
    # a traceback (list of calls). This needs to be pre-formatted because
    # rjson::toJSON can't handle call objects.
    if (!is.null(test_results[[i]]$results[[j]]$trace)) {
      test_results[[i]]$results[[j]]$trace <- format(test_results[[i]]$results[[j]]$trace)
    }

    # Check result for MarkUs metadata
    if ("markus_tag" %in% names(attributes(result))) {
      tags <- append(tags, attr(result, "markus_tag"))
      test_results[[i]]$results[[j]]$type <- "metadata"
    }
    if ("markus_annotation" %in% names(attributes(result))) {
      annotations <- append(annotations, list(attr(result, "markus_annotation")))
      test_results[[i]]$results[[j]]$type <- "metadata"
    }
    if ("markus_overall_comments" %in% names(attributes(result))) {
      overall_comments <- append(overall_comments, attr(result, "markus_overall_comments"))
      test_results[[i]]$results[[j]]$type <- "metadata"
    }
  }
}

json <- rjson::toJSON(list(
  test_results = test_results,
  tags = tags,
  annotations = annotations,
  overall_comments = overall_comments
))
sink()
cat(json)
