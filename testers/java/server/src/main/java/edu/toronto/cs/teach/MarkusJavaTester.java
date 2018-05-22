package edu.toronto.cs.teach;

import com.google.gson.Gson;
import org.jetbrains.annotations.NotNull;
import org.jetbrains.annotations.Nullable;
import org.junit.platform.engine.TestExecutionResult;
import org.junit.platform.engine.TestSource;
import org.junit.platform.engine.discovery.ClassNameFilter;
import org.junit.platform.engine.discovery.DiscoverySelectors;
import org.junit.platform.engine.support.descriptor.MethodSource;
import org.junit.platform.launcher.Launcher;
import org.junit.platform.launcher.LauncherDiscoveryRequest;
import org.junit.platform.launcher.TestExecutionListener;
import org.junit.platform.launcher.TestIdentifier;
import org.junit.platform.launcher.core.LauncherDiscoveryRequestBuilder;
import org.junit.platform.launcher.core.LauncherFactory;

import java.io.IOException;
import java.io.OutputStream;
import java.io.PrintStream;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.*;

public class MarkusJavaTester {

    private class TestResult {
        private @NotNull String name;
        private @NotNull TestExecutionResult.Status status;
        private @Nullable String description;
        private @Nullable String message;
    }

    private @NotNull String[] testClasses;
    private @NotNull List<TestResult> results;

    public MarkusJavaTester(@NotNull String[] testFiles) {

        this.testClasses = new String[testFiles.length];
        for (int i = 0; i < testFiles.length; i++) {
            testClasses[i] = testFiles[i].split("\\.")[0];
        }
        this.results = new ArrayList<>();
    }

    private void run() {

        // redirect stdout and stderr
        PrintStream outOrig = System.out, errOrig = System.err;
        System.setOut(new PrintStream(new OutputStream() {
            public void write(int b) throws IOException {}
        }));
        System.setErr(new PrintStream(new OutputStream() {
            public void write(int b) throws IOException {}
        }));
        // run tests
        Set<Path> classpath = new HashSet<>();
        classpath.add(Paths.get("."));
        LauncherDiscoveryRequest request = LauncherDiscoveryRequestBuilder.request()
            .selectors(DiscoverySelectors.selectClasspathRoots(classpath))
            .filters(ClassNameFilter.includeClassNamePatterns(this.testClasses))
            .build();
        Launcher launcher = LauncherFactory.create();
        launcher.registerTestExecutionListeners(new TestExecutionListener() {
            @Override
            public void executionFinished(TestIdentifier testIdentifier, TestExecutionResult testExecutionResult) {
                // record a single test result
                if (testIdentifier.isContainer()) {
                    return;
                }
                TestSource source = testIdentifier.getSource().orElse(null);
                if (source == null || !(source instanceof MethodSource)) {
                    return;
                }
                TestResult result = new TestResult();
                String className = ((MethodSource) source).getClassName();
                String methodName = ((MethodSource) source).getMethodName();
                result.name = className + "." + methodName;
                if (!testIdentifier.getDisplayName().equals(methodName + "()")) { // @DisplayName annotation
                    result.description = testIdentifier.getDisplayName();
                }
                result.status = testExecutionResult.getStatus();
                testExecutionResult.getThrowable().ifPresent(t -> result.message = t.getMessage());
                results.add(result);
            }
        });
        launcher.execute(request);
        // restore stdout and stderr, then print results
        System.setOut(outOrig);
        System.setErr(errOrig);
        System.out.print(new Gson().toJson(this.results));
    }

    public static void main(String[] args) {

        MarkusJavaTester tester = new MarkusJavaTester(args);
        tester.run();
    }

}
