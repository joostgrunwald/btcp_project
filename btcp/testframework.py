import unittest
import time
import sys
import filecmp
import threading
import bTCP_server
import bTCP_client
import File
import Runners

"""This exposes a constant bytes object called TEST_BYTES_128MIB which, as the
name suggests, is 128 MiB in size. You can send it, receive it, and check it
for equality on the receiving end.

Pycharm may complain about an unresolved reference. This is a lie. It simply
cannot deal with a python source file this large so it cannot resolve the
reference. Python itself will run it fine, though.

You can also use the file large_input.py as-is for file transfer.
"""
from large_input import TEST_BYTES_128MIB

TIMEOUT = 100
WINSIZE = 100
INTF = "lo"
NETEM_ADD     = "sudo tc qdisc add dev {} root netem".format(INTF)
NETEM_CHANGE  = "sudo tc qdisc change dev {} root netem {}".format(INTF, "{}")
NETEM_DEL     = "sudo tc qdisc del dev {} root netem".format(INTF)
NETEM_CORRUPT = "corrupt 1%"
NETEM_DUP     = "duplicate 10%"
NETEM_LOSS    = "loss 10% 25%"
NETEM_REORDER = "delay 20ms reorder 25% 50%"
NETEM_DELAY   = "delay " + str(TIMEOUT) + "ms 20ms"
NETEM_ALL     = "{} {} {} {}".format(NETEM_CORRUPT, NETEM_DUP, NETEM_LOSS, NETEM_REORDER)

def run_command_with_output(command, input=None, cwd=None, shell=True):
    """run command and retrieve output"""
    import subprocess
    try:
        process = subprocess.Popen(command, cwd=cwd, shell=shell, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
    except Exception as e:
        print("problem running command : \n   ", command, "\n problem: ", e, file=sys.stderr)


    [stdoutdata, stderrdata] = process.communicate(input)  # no pipes set for stdin/stdout/stdout streams so does effectively only just wait for process ends  (same as process.wait()

    if process.returncode:
        print(stderrdata, file=sys.stderr)
        print("\nproblem running command : \n   ", command, "\n return value: ", process.returncode, file=sys.stderr)


    return stdoutdata

def run_command(command,cwd=None, shell=True):
    """run command with no output piping"""
    import subprocess
    process = None
    try:
        process = subprocess.Popen(command, shell=shell, cwd=cwd)
        print("\nProcess started:", file=sys.stderr)
        print(process, file=sys.stderr)
    except Exception as e:
        print("problem running command : \n   ", command, "\n problem: ", e, file=sys.stderr)

    process.communicate()  # wait for the process to end

    if process.returncode:
        print("problem running command : \n   ", command, "\n return value: ", process.returncode, file=sys.stderr)
        

class TestbTCPFramework(unittest.TestCase):
    """Test cases for bTCP"""
    
    def setUp(self):
        """Setup before each test

        This is an example test setup that uses the client and server process
        to test your application. Feel free to use a different test setup.
        """
        print("\nSETTING UP TEST ENVIRONMENT\n", file=sys.stderr)
        # ensure we can initialize a clean netem
        print("\nCLEANING NETEM IF PRESENT. ERROR IS NOT A PROBLEM.\n", file=sys.stderr)
        run_command(NETEM_DEL)
        # default netem rule (does nothing)
        print("\nSETTING UP NEW NETEM\n", file=sys.stderr)
        run_command(NETEM_ADD)

        outputfilename = "largeoutput.txt"
        inputfilename = "largeinput.txt"
        # launch localhost server
        self.serverrunner = Runners.ServerRunner(WINSIZE, TIMEOUT, outputfilename)
        self.clientrunner = Runners.ClientRunner(WINSIZE, TIMEOUT, inputfilename)
        self.clientfile = File.File(inputfilename)
        self.serverfile = File.File(outputfilename)
        # self.assertFalse(self.server.connected)

    def tearDown(self):
        """Clean up after testing"""
        # clean the environment
        run_command(NETEM_DEL)
        # close server
        # self.assertTrue(self.server.finished)

    def test_ideal_network(self):
        """reliability over an ideal framework"""
        # setup environment (nothing to set)
        self.serverrunner.start()
        # launch localhost client connecting to server
        # client sends content to server
        # server receives content from client
        self.clientrunner.start()

        self.clientrunner.join()
        self.serverrunner.server.end()
        self.serverrunner.join()

        # content received by server matches the content sent by client
        equalFile = self.clientrunner.client.file.check_files(self.serverfile)
        self.assertTrue(equalFile)

    def test_flipping_network(self):
        """reliability over network with bit flips 
        (which sometimes results in lower layer packet loss)"""
        # setup environment
        run_command(NETEM_CHANGE.format("corrupt 1%"))
        self.serverrunner.start()
        # launch localhost client connecting to server
        # client sends content to server
        # server receives content from client
        self.clientrunner.start()

        self.clientrunner.join()
        self.serverrunner.server.end()
        self.serverrunner.join()

        # content received by server matches the content sent by client
        equalFile = self.clientrunner.client.file.check_files(self.serverfile)
        self.assertTrue(equalFile)

    def test_duplicates_network(self):
        """reliability over network with duplicate packets"""
        # setup environment
        run_command(NETEM_CHANGE.format("duplicate 10%"))
        self.serverrunner.start()
        # launch localhost client connecting to server
        # client sends content to server
        # server receives content from client
        self.clientrunner.start()

        self.clientrunner.join()
        self.serverrunner.server.end()
        self.serverrunner.join()

        # content received by server matches the content sent by client
        equalFile = self.clientrunner.client.file.check_files(self.serverfile)
        self.assertTrue(equalFile)

    def test_lossy_network(self):
        """reliability over network with packet loss"""
        # setup environment
        run_command(NETEM_CHANGE.format("loss 10% 25%"))
        self.serverrunner.start()
        # launch localhost client connecting to server
        # client sends content to server
        # server receives content from client
        self.clientrunner.start()

        self.clientrunner.join()
        self.serverrunner.server.end()
        self.serverrunner.join()

        # content received by server matches the content sent by client
        equalFile = self.clientrunner.client.file.check_files(self.serverfile)
        self.assertTrue(equalFile)

    def test_reordering_network(self):
        """reliability over network with packet reordering"""
        # setup environment
        run_command(NETEM_CHANGE.format("delay 20ms reorder 25% 50%"))
        self.serverrunner.start()
        # launch localhost client connecting to server
        # client sends content to server
        # server receives content from client
        self.clientrunner.start()

        self.clientrunner.join()
        self.serverrunner.server.end()
        self.serverrunner.join()

        # content received by server matches the content sent by client
        equalFile = self.clientrunner.client.file.check_files(self.serverfile)
        self.assertTrue(equalFile)
        
    def test_delayed_network(self):
        """reliability over network with delay relative to the timeout value"""
        # setup environment
        run_command(NETEM_CHANGE.format(f"delay {str(TIMEOUT)}ms 20ms"))
        self.serverrunner.start()
        # launch localhost client connecting to server
        # client sends content to server
        # server receives content from client
        self.clientrunner.start()

        self.clientrunner.join()
        self.serverrunner.server.end()
        self.serverrunner.join()

        # content received by server matches the content sent by client
        equalFile = self.clientrunner.client.file.check_files(self.serverfile)
        self.assertTrue(equalFile)
    
    def test_allbad_network(self):
        """reliability over network with all of the above problems"""

        # setup environment
        run_command(NETEM_CHANGE.format("corrupt 1% duplicate 10% loss 10% 25% delay 20ms reorder 25% 50%"))
        self.serverrunner.start()
        # launch localhost client connecting to server
        # client sends content to server
        # server receives content from client
        self.clientrunner.start()

        self.clientrunner.join()
        self.serverrunner.server.end()
        self.serverrunner.join()

        # content received by server matches the content sent by client
        equalFile = self.clientrunner.client.file.check_files(self.serverfile)
        self.assertTrue(equalFile)

  
#    def test_command(self):
#        #command=['dir','.']
#        out = run_command_with_output("dir .")
#        print(out)
        

if __name__ == '__main__':
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="bTCP tests")
    parser.add_argument("-w", "--window",
                        help="Define bTCP window size used",
                        type=int, default=100)
    parser.add_argument("-t", "--timeout",
                        help="Define the timeout value used (ms)",
                        type=int, default=TIMEOUT)
    args, extra = parser.parse_known_args()
    TIMEOUT = args.timeout
    WINSIZE = args.window

    # Pass the extra arguments to unittest
    sys.argv[1:] = extra

    # Start test suite
    unittest.main()
