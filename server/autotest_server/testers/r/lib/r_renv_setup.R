# Script to install dependencies for R tester environment using a renv.lock file. 

# Install renv if not already installed
if (!("renv" %in% rownames(installed.packages()))) {
  install.packages("renv")
}
library(renv)

# Set the path for the renv.lock file and the env_dir directory
lockfile <- commandArgs(trailingOnly = TRUE)[1]
env_dir <- commandArgs(trailingOnly = TRUE)[2]

if (!file.exists(lockfile)) {
  stop("renv.lock file not found: ", lockfile)
}

# Initialize the renv environment and restore dependencies from the lockfile
renv::restore(lockfile = lockfile, library = env_dir)
