README
======

Drop this into a Jenkins project.

Configure all the Gerrit triggers you want on the project.

Configure the project to build using `./check.py`.

Setup the following environment variables at a minimal:

    JIRA_SERVER
    JIRA_USERNAME
    JIRA_PASSWORD

You may also want to change the following:

    TOKENS

`TOKENS` may contain a comma-separated list of magic keywords that allow a
commit to be accepted regardless of issues. By default is contains `trivial`,
`merge`, `hotyb` (hold on to your butt), and `wdil` (we'll do it live).

    GERRIT_USERNAME

`GERRIT_USERNAME` may be used to override the username used to login to Gerrit.
Otherwise, the current user will be used.

That's it!
