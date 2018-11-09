#define _GNU_SOURCE
#include <unistd.h>
#include <signal.h>
#include <stdio.h>

int main(int argc, char *argv[])
{
	remove(argv[0]);
	uid_t reaper_uid = getuid();
	uid_t worker_uid = geteuid();
	if ( setresuid(reaper_uid, worker_uid, reaper_uid) < 0 ) 
	{
		return -1;
	}
	kill(-1, SIGKILL);
	return 0;
}