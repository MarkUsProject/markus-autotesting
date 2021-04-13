#!/usr/bin/env racket
#lang racket

(require rackunit)
(require rackunit/text-ui)
(require rackunit/private/check-info)
(require json)
(require racket/cmdline)
(require syntax/modcode)

(define-syntax-rule (require-names path name ...)
  (begin
    (require path)
    (if-defined name
                (void)
                (define (name) (error (format "Name ~a could not be imported" (quote name)))))
    ...))
  
; struct containing the required values from running a single test
(struct autotester-result (name status message))

; convert a autotester-result struct to hash
(define (autotester-result->hash r)
  (hasheq 'name (autotester-result-name r)
          'status (autotester-result-status r)
          'message (autotester-result-message r)))

; convert test result info to hash
(define (check-infos->hash stack)
  (make-immutable-hash
   (map (lambda (ci) (cons (check-info-name ci) (check-info-value ci))) stack)))

; create result hash from a successful test
(define (make-success test-case-name result)
  (autotester-result->hash
    (autotester-result test-case-name "pass" "")))

; create result hash from a failed autotester test
(define (make-failure test-case-name result)
  (let* ( [failure-data
            (if (exn:test:check? result)
              (check-infos->hash (exn:test:check-stack result))
              (hash))]
          [message (hash-ref failure-data 'message "")])
        (autotester-result->hash
          (autotester-result
            test-case-name 
            "fail" 
            (format "~s" message)))))

; create result hash from a test that caused an error
(define (make-error test-case-name result)
  (autotester-result->hash
    (autotester-result test-case-name "error" (format "~s" (exn-message result)))))

; create result hash depending for a test depending on whether it was a
; success, failure, or caused an error (see above)
(define (show-test-result result)
  (match result
    [(test-success test-case-name result) (make-success test-case-name result)]
    [(test-failure test-case-name result) (make-failure test-case-name result)]
    [(test-error test-case-name result) (make-error test-case-name result)]))

; define a custom error type (currently not used)
(define (raise-autotester-error message [error-type 'autotester-error])
  (raise (error error-type message)))

; main module: parses command line arguments, runs tests specified by these arguments
; and prints the results to stdout as a json string.
(module+ main
  (define test-suite-sym 'all-tests)
  (define test-file 
    (command-line 
      #:program "compiler"
      #:once-each
      [("-t" "--test-suite") ts "Name of the test suite to run in the test-file"
                                (set! test-suite-sym (string->symbol ts))]
      #:args (test-file)
      test-file))
  
  (define test-results null)
  (let  ([s (current-error-port)])
        (parameterize ([current-output-port s])
          (set! test-results 
            (run-test (dynamic-require/expose (string->path test-file) test-suite-sym)))))
  (write-json (map show-test-result test-results)))
