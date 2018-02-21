require 'httparty'
require 'open3'

class AutomatedTestsServer

  # the user running this Resque worker should be:
  # a) the user running MarkUs if ATE_SERVER_FILES_USERNAME == 'localhost' (development)
  # b) a real separate user ATE_SERVER_FILES_USERNAME otherwise (production)
  def self.perform(markus_address, user_api_key, server_api_key, test_username, test_scripts, files_path, tests_path,
                   results_path, assignment_id, group_id, group_repo_name, submission_id)

    # move files to the test location (if needed)
    if files_path != tests_path
      unless Dir.exists?(tests_path)
        # this should only happen in development
        # (a production environment would already have the tests dir with the appropriate owners and permissions)
        FileUtils.mkdir_p(tests_path, {mode: 01770}) # rwxrwx--T for the tests dir
      end
      FileUtils.cp_r("#{files_path}/.", tests_path) # includes hidden files
      FileUtils.rm_rf(files_path)
    end
    # give permissions: the test user can create new files but not modify/delete submission files and test scripts
    # (to fully work, the tests dir must be rwxrwx--T ATE_SERVER_FILES_USERNAME:test_username)
    # submission files + test scripts: u and g are the server user (who copied the files), o is the test user
    files_and_dirs = Dir.glob(File.join(tests_path, '*'), File::FNM_DOTMATCH) -
                     [File.join(tests_path, '.'), File.join(tests_path, '..')]
    FileUtils.chmod_R('u+w,go-w,ugo-x+rX', files_and_dirs, {force: true}) # rwxr-xr-x for dirs, rw-r--r-- for files
    FileUtils.chmod('ugo+x', test_scripts.map {|script| File.join(tests_path, script['file_name'])}) # rwxr-xr-x for test scripts

    # run tests
    all_output = '<testrun>'
    all_errors = ''
    pid = nil
    test_scripts.each do |script|
      run_command = "cd '#{tests_path}'; "\
                    "./'#{script['file_name']}' #{markus_address} #{user_api_key} #{assignment_id} #{group_id} "\
                                                 "#{group_repo_name}"
      unless test_username.nil?
        run_command = "sudo -u #{test_username} -- bash -c \"#{run_command}\""
      end
      output = ''
      errors = ''
      start_time = Time.now
      Open3.popen3(run_command, pgroup: true) do |stdin, stdout, stderr, thread|
        pid = thread.pid
        stdin.close
        # mimic capture3 to read safely and capture each line as it comes so that
        # these threads don't hang or raise an error if we have to kill them early
        stdout_thread = Thread.new { stdout.each { |line| output << line + $/} }
        stderr_thread = Thread.new { stderr.each { |line| errors << line + $/} }
        if !thread.join(script['timeout']) # still running, let's kill the process group
          if test_username.nil?
            Process.kill('KILL', -pid)
          else
            Open3.capture3("sudo -u #{test_username} -- bash -c \"kill -KILL -#{pid}\"")
          end
          # prepend errors with output up to when the timeout occured
          unless output.empty?
            errors = ["STDOUT BEFORE TIMEOUT OCCURED:", output, "ERRORS:", errors].join($/)
          end
          # timeout output
          output = "
<test>
  <name>All tests</name>
  <input></input>
  <expected></expected>
  <actual>#{script['timeout']} seconds timeout expired</actual>
  <marks_earned>0</marks_earned>
  <marks_total>0</marks_total>
  <status>error</status>
</test>"
        end
        # kill threads otherwise stdout.each will raise an IOError 
        # once the pipes are closed at the end of this block
        stdout_thread.kill
        stderr_thread.kill
      end
      run_time = (Time.now - start_time) * 1000.0 # milliseconds
      all_output += "
<test_script>
  <file_name>#{script['file_name']}</file_name>
  <time>#{run_time.to_i}</time>
  #{output}
</test_script>"
      all_errors += errors
    end
    all_output += "\n</testrun>"

    # store results
    time = Time.now.to_f * 1000.0 # milliseconds
    results_path = File.join(results_path, markus_address.gsub('/', '_'), "a#{assignment_id}", "g#{group_id}",
                             "s#{submission_id}", "run_#{time.to_i}_#{pid}")
    FileUtils.mkdir_p(results_path)
    File.write("#{results_path}/output.txt", all_output)
    all_errors.strip!
    unless all_errors == ''
      File.write("#{results_path}/errors.txt", all_errors)
    end

    # cleanup: kill spawned processes and delete all files (including nested files created by the test user)
    unless test_username.nil?
      clean_command = "chmod -Rf ugo+rwX '#{tests_path}'; "\
                      "killall -KILL -u #{test_username}"
      Open3.capture3("sudo -u #{test_username} -- bash -c \"#{clean_command}\"")
    end
    FileUtils.rm_rf(tests_path)

    # send results back to markus by api
    api_url = "#{markus_address}/api/assignments/#{assignment_id}/groups/#{group_id}/test_script_results"
    # HTTParty needs strings as hash keys, or it chokes
    options = {:headers => {
                   'Authorization' => "MarkUsAuth #{server_api_key}",
                   'Accept' => 'application/json'},
               :body => {
                   'requested_by' => user_api_key,
                   'test_scripts' => test_scripts.map {|script| script['file_name']},
                   'test_output' => all_output}}
    unless all_errors == ''
      options[:body]['test_errors'] = all_errors
    end
    unless submission_id.nil?
      options[:body]['submission_id'] = submission_id
    end
    HTTParty.post(api_url, options)
  end

end
