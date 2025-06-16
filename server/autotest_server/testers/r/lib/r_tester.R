sink(file="/dev/null")
library(testthat)
library(rjson)
args <- commandArgs(TRUE)
test_file <- args[1]
generate_html <- Sys.getenv("GENERATE_RMD_HTML") == "true"

if (generate_html && grepl("\\.Rmd$", test_file)) {
  if (!requireNamespace("rmarkdown", quietly = TRUE)) {
    stop("rmarkdown package not installed.")
  }

  output_file <- sub("\\.Rmd$", ".html", test_file)
  rmarkdown::render(test_file, output_file = output_file, quiet = TRUE)

  json <- rjson::toJSON(list(status = "Rmd rendered", output_file = output_file))
  sink()
  cat(json)
  quit("no")
}

test_results <- testthat::test_file(test_file, reporter = testthat::ListReporter)
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
  }
}
json <- rjson::toJSON(test_results)
sink()
cat(json)
