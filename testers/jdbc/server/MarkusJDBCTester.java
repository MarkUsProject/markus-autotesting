import java.io.IOException;
import java.io.OutputStream;
import java.io.PrintStream;
import java.io.StringWriter;
import java.sql.PreparedStatement;
import java.text.MessageFormat;
import java.util.HashMap;
import java.util.Map;

import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.transform.OutputKeys;
import javax.xml.transform.Transformer;
import javax.xml.transform.TransformerFactory;
import javax.xml.transform.dom.DOMSource;
import javax.xml.transform.stream.StreamResult;

import org.w3c.dom.Document;
import org.w3c.dom.Text;

public class MarkusJDBCTester {

	private static class TestResult {
		String msg;
		String status;
		public TestResult(String msg, String status) {
			this.msg = msg;
			this.status = status;
		}
	}

	private static String escapeXml(String target) {

		try {
			Document document = DocumentBuilderFactory.newInstance().newDocumentBuilder().newDocument();
			Text text = document.createTextNode(target);
			Transformer transformer = TransformerFactory.newInstance().newTransformer();
			DOMSource source = new DOMSource(text);
			StringWriter writer = new StringWriter();
			StreamResult result = new StreamResult(writer);
			transformer.setOutputProperty(OutputKeys.OMIT_XML_DECLARATION, "yes");
			transformer.transform(source, result);
			return writer.toString();
		}
		catch (Exception e) {
			return target;
		}
	}

	private static void printTestResult(String name, String status, String output, int pointsAwarded, Integer pointsTotal) {

		if (pointsTotal != null && pointsTotal <= 0) {
			throw new IllegalArgumentException("The total points must be > 0");
		}
		if (pointsAwarded < 0) {
			throw new IllegalArgumentException("The points awarded must be >= 0");
		}
		if (pointsTotal != null && pointsAwarded > pointsTotal) {
			throw new IllegalArgumentException("The points awarded must be <= the total points");
		}

		String outputEscaped = MarkusJDBCTester.escapeXml(output.replace("\\x00", ""));
		String info = (pointsTotal == null) ? name : "[" + pointsAwarded + "/" + pointsTotal + "] " + name;
		System.err.print(
"<test>\n" +
	"<name>" + info + "</name>\n" +
	"<input></input>\n" +
	"<expected></expected>\n" +
	"<actual>" + outputEscaped + "</actual>\n" +
	"<marks_earned>" + pointsAwarded + "</marks_earned>\n" +
	"<status>" + status + "</status>\n" +
"</test>");
	}

	private static void printTestError(String name, String message, Integer pointsTotal) {

		MarkusJDBCTester.printTestResult(name, "error", message, 0, pointsTotal);
	}

	private static void printFileHeader(String testDataName, String status, String feedback) {

		System.out.print("========== " + testDataName + ": " + status.toUpperCase() + " ==========\n\n");
		if (!feedback.equals("")) {
			System.out.print("## Feedback: " + feedback + "\n\n");
		}
	}

	private static void printFileError(String testDataName, String feedback) {

		MarkusJDBCTester.printFileHeader(testDataName, "error", feedback);
		System.out.print("\n");
	}

	private static final Map<String, String> ERROR_MSGS = new HashMap<>();
	static {
		ERROR_MSGS.put("bad_connection", "connectDB did not create a valid connection to the database");
		ERROR_MSGS.put("ex_connection", "Connection to the database failed with an exception: ''{0}''");
		ERROR_MSGS.put("bad_disconnection", "disconnectDB did not close the database connection properly");
		ERROR_MSGS.put("ex_disconnection", "Disconnection from the database failed with an exception: ''{0}''");
		ERROR_MSGS.put("bad_output", "Expected the output to be ''{0}'' instead of ''{1}''");
		ERROR_MSGS.put("ex_output", "The test failed with an exception: ''{0}''");
	}
	private static final String CONNECTION_TEST = "Connection Test";

	private String oracleDatabase;
	private String testDatabase;
	private String userName;
	private String userPassword;
	private SubmissionOracle oracle;
	private Submission test;

	public MarkusJDBCTester(String oracleDatabase, String testDatabase, String userName, String userPassword) {

		this.oracleDatabase = oracleDatabase;
		this.testDatabase = testDatabase;
		this.userName = userName;
		this.userPassword = userPassword;
	}

	private TestResult initDB(String dataName) {

		try {
			this.oracle = new SubmissionOracle();
			this.test = new Submission();
			final String JDBC_PREAMBLE = "jdbc:postgresql://localhost:5432/";
			boolean testConnected = this.test.connectDB(JDBC_PREAMBLE + this.testDatabase, this.userName, this.userPassword);
			if (!testConnected || this.test.connection == null || !this.test.connection.isValid(0)) {
				String msg = ERROR_MSGS.get("bad_connection");
				return new TestResult(msg, "fail");
			}
			this.oracle.connectDB(JDBC_PREAMBLE + this.oracleDatabase, this.userName, this.userPassword);
			if (dataName != null) {
				String oracleSchema = "set search_path to " + dataName.toLowerCase();
				PreparedStatement ps = this.oracle.connection.prepareStatement(oracleSchema);
				ps.execute();
				ps.close();
			}
			return new TestResult("", "pass");
		}
		catch (Exception e) {
			String msg = MessageFormat.format(ERROR_MSGS.get("ex_connection"), e.getMessage());
			return new TestResult(msg, "fail");
		}
	}

	private TestResult closeDB() {

		try {
			boolean testDisconnected = this.test.disconnectDB();
			if (!testDisconnected || (this.test.connection != null && !this.test.connection.isClosed())) {
				String msg = ERROR_MSGS.get("bad_disconnection");
				try { // try to close manually, but the error should still be bad_disconnection
					if (this.test.connection != null) {
						this.test.connection.close();
					}
				}
				catch (Exception e) {}
				return new TestResult(msg, "fail");
			}
			return new TestResult("", "pass");
		}
		catch (Exception e) {
			String msg = MessageFormat.format(ERROR_MSGS.get("ex_disconnection"), e.getMessage());
			return new TestResult(msg, "fail");
		}
		finally {
			try {
				this.oracle.disconnectDB();
			}
			catch (Exception e) {}
		}
	}

	public void run(String dataFile, String testName, int pointsTotal) {

		String dataName = null;
		String testDataName = "JAVA " + testName;
		if (!testName.equals(MarkusJDBCTester.CONNECTION_TEST)) {
			dataName = dataFile.split("\\.")[0];
			testDataName += " + " + dataName;
		}
		int pointsAwarded = 0;
		TestResult testResult = null, closeResult = null;

		// redirect stdout and stderr
		PrintStream outOrig = System.out, errOrig = System.err;
		System.setOut(new PrintStream(new OutputStream() {
			public void write(int b) throws IOException {}
		}));
		System.setErr(new PrintStream(new OutputStream() {
			public void write(int b) throws IOException {}
		}));
		// run tests
		testResult = this.initDB(dataName);
		if (testResult.status.equals("pass")) {
			switch (testName) {
//				case "X":
//					testResult = this.testX(dataName);
//					break;
				default:
					break;
			}
		}
		pointsAwarded = (testResult.status.equals("pass")) ? pointsTotal : 0; // closeDB() doesn't matter..
		closeResult = this.closeDB();
		if (testName.equals(MarkusJDBCTester.CONNECTION_TEST) && testResult.status.equals("pass")) {
			testResult = closeResult;
			pointsAwarded = (testResult.status.equals("pass")) ? pointsTotal : 0; // ..unless it's the connection test
		}
		// restore stdout and stderr
		System.setOut(outOrig);
		System.setErr(errOrig);
		// print results
		MarkusJDBCTester.printTestResult(testDataName, testResult.status, testResult.msg, pointsAwarded, pointsTotal);
		MarkusJDBCTester.printFileHeader(testDataName, testResult.status, testResult.msg);
	}

	public static void main(String args[]) {

		final String ORACLE_DATABASE = args[0];
		final String TEST_DATABASE = args[1];
		final String USER_NAME = args[2];
		final String USER_PASSWORD = args[3];
		final String TEST_NAME = args[4];
		final String DATA_FILE = args[5];
		final int POINTS_TOTAL = Integer.valueOf(args[6]);

		MarkusJDBCTester tester = new MarkusJDBCTester(ORACLE_DATABASE, TEST_DATABASE, USER_NAME, USER_PASSWORD);
		tester.run(DATA_FILE, TEST_NAME, POINTS_TOTAL);
	}

}