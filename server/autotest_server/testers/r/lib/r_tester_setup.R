# Script to install dependencies for R tester environment.
# Parses a dependency string in the format specified for R package DESCRIPTION
# files. See https://cran.r-project.org/doc/manuals/r-release/R-exts.html#Package-Dependencies.

# First, load remotes package to help with installing other packages
if (!("remotes" %in% installed.packages())) {
  install.packages("remotes")
}
library(remotes)


main <- function() {
  # Tester dependencies
  # rjson v0.2.20 is required to support R v3.x
  deps <- "testthat, rjson (== 0.2.20)"

  # Additional dependencies for test environment from command-line args
  args <- commandArgs(TRUE)
  all_deps <- do.call(paste, c(deps, as.list(args), sep=","))

  # Parse dependencies and install
  deps <- parse_deps(all_deps)
  apply(deps, 1, install_dep)
}


install_dep <- function(row) {
  name <- row["name"]
  compare <- row["compare"]
  version <- row["version"]

  if (grepl("::", name, fixed = TRUE)) {
    res <- strsplit(name, "::")[[1]]
    remote_type <- res[[1]]
    name <- res[[2]]
  } else if (grepl("/", name, fixed = TRUE)) {
    remote_type <- "github"
  } else {
    remote_type <- NA_character_
  }

  # Check if package is already installed
  # TODO: make this work for remote packages (with '/' in the name)
  if (name %in% installed.packages() &&
      (is.na(version) || version_satisfies_criterion(name, compare, version))) {
      print(paste("Skipping '", name, "': package already installed", sep=""))
      return()
  }

  if (!is.na(remote_type)) {
    install_func <- getFromNamespace(paste("install_", remote_type, sep = ""), "remotes")
    name <- install_func(name) # install_func returns the package name
  } else if (!is.na(version)) {
    install_version(name, version = paste(compare, version, sep =" "))
  } else {
    install.packages(name)
  }

  if (!(name %in% installed.packages())) {
    stop("ERROR: Could not install package ", name)
  }
}


## based on https://github.com/r-lib/remotes/blob/main/R/install-version.R
version_satisfies_criterion <- function(name, compare, version) {
  installed_version <- packageVersion(name)
  get(compare)(installed_version, version)
}


## copied from https://github.com/r-lib/remotes/blob/main/R/package-deps.R
parse_deps <- function(string) {
  if (is.null(string)) return()
  stopifnot(is.character(string), length(string) == 1)
  if (grepl("^\\s*$", string)) return()

  # Split by commas with surrounding whitespace removed
  pieces <- strsplit(string, "[[:space:]]*,[[:space:]]*")[[1]]

  # Get the names
  names <- gsub("\\s*\\(.*?\\)", "", pieces)
  names <- gsub("^\\s+|\\s+$", "", names)

  # Get the versions and comparison operators
  versions_str <- pieces
  have_version <- grepl("\\(.*\\)", versions_str)
  versions_str[!have_version] <- NA

  compare  <- sub(".*\\(\\s*(\\S+)\\s+.*\\s*\\).*", "\\1", versions_str)
  versions <- sub(".*\\(\\s*\\S+\\s+(\\S*)\\s*\\).*", "\\1", versions_str)

  # Check that non-NA comparison operators are valid
  compare_nna   <- compare[!is.na(compare)]
  compare_valid <- compare_nna %in% c(">", ">=", "==", "<=", "<")
  if(!all(compare_valid)) {
    stop("Invalid comparison operator in dependency: ",
      paste(compare_nna[!compare_valid], collapse = ", "))
  }

  deps <- data.frame(name = names, compare = compare,
    version = versions, stringsAsFactors = FALSE)

  # Remove R dependency
  deps[names != "R", ]
}


main()
