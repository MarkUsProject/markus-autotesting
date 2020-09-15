import org.junit.DisplayName;
import org.junit.Test;

import static org.junit.Assertions.assertTrue;

public class Test1 {

    Submission submission = new Submission();

    @Test
    @DisplayName("This test should pass")
    public void testPasses() {
        assertTrue(submission.returnTrue());
    }

    @Test
    @DisplayName("This test should fail")
    public void testFails() {
        assertTrue(submission.returnFalse());
    }

}
