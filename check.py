#!/usr/bin/env python

import sys
import re
import os
import tempfile
import atexit
import shutil
import subprocess
import getpass

from jira.client import JIRA

# Configuration.
TOKENS = (os.getenv("TOKENS") or "wdil,trivial,merge,hotyb").split(",")
JIRA_SERVER = os.getenv("JIRA_SERVER")
JIRA_USERNAME = os.getenv("JIRA_USERNAME")
JIRA_PASSWORD = os.getenv("JIRA_PASSWORD")
GERRIT_USERNAME = os.getenv("GERRIT_USERNAME") or getpass.getuser()

# Check that we have JIRA configuration.
if not JIRA_SERVER or not JIRA_USERNAME or not JIRA_PASSWORD:
    sys.stderr.write("No JIRA information provided.\n")
    sys.stderr.write("Need JIRA_SERVER, JIRA_USERNAME, JIRA_PASSWORD.\n")
    sys.exit(0)

# From the gerrit plugin.
host = os.getenv("GERRIT_HOST")
port = os.getenv("GERRIT_PORT")
proto = os.getenv("GERRIT_PROTO")
project = os.getenv("GERRIT_PROJECT")
changeset = os.getenv("GERRIT_PATCHSET_REVISION")
refspec = os.getenv("GERRIT_REFSPEC")
subject = os.getenv("GERRIT_CHANGE_SUBJECT")
author_name = os.getenv("GERRIT_CHANGE_OWNER_NAME") or "unknown"
author_email = os.getenv("GERRIT_CHANGE_OWNER_EMAIL") or "unknown"
message = os.getenv("GERRIT_CHANGE_COMMIT_MESSAGE") or ""
change_url = os.getenv("GERRIT_CHANGE_URL")
event_type = os.getenv("GERRIT_EVENT_TYPE")

# Check if we were triggered by gerrit.
if not subject or not project or not event_type:
    sys.stderr.write("No Gerrit information available.\n")
    sys.stderr.write("Need GERRIT_CHANGE_SUBJECT, GERRIT_PROJECT and GERRIT_EVENT_TYPE.\n")
    sys.exit(0)

# Dump environment.
for key, val in os.environ.items():
   print "%s=%s" % (key, val)

# Build our regular expressions.
ISSUERE = "(^|[ :;,.(])([A-Z]+-[1-9][0-9]*)($|[ :;,.)])"
TOKENRE = "(^|[ :;,.(])(" + "|".join(TOKENS) + ")($|[ :;,.)])"

# Connect to JIRA (fast fail).
options = { "server": JIRA_SERVER }
jira = JIRA(options, basic_auth=(JIRA_USERNAME, JIRA_PASSWORD))

def extract_info(output):
    metadata = {}
    subject = None
    message = ""
    issues = []
    tokens = []

    for line in output.split("\n"):
        # Skip empty lines.
        if not line:
            continue

        # Skip the commit.
        m = re.match("^commit (.*)$", line)
        if m:
            continue

        # Extract metadata.
        m = re.match("^([^: ]*): (.*)$", line)
        if m:
            metadata[m.group(1).lower()] = m.group(2)
            continue

        # Extract the message.
        m = re.match("^    (.*)$", line)
        if m:
            if subject is None:
                subject = m.group(1)

                # Only add tokens for the subject.
                if len(TOKENS) > 0:
                    for match in re.finditer(TOKENRE, line, re.IGNORECASE):
                        tokens.append(match.group(2))

            else:
                message = message + "\n" + m.group(1)

            # Add all matching issues.
            for match in re.finditer(ISSUERE, line):
                issues.append(match.group(2))
        else:
            break

    return (metadata, subject, message, issues, tokens)

# Construct our local copy.
dirname = "repos/%s" % project

# Clone it if the information is available.
if host and port and proto and refspec:
    # Create a local directory for our checkout.
    try:
        os.makedirs("repos")
    except OSError:
        # Exists.
        pass

    # Clone if we need to.
    if not os.path.exists(dirname):
        git_url = "%s://%s@%s:%d/%s" % (proto, GERRIT_USERNAME, host, int(port), project)
        rc = subprocess.call(["git", "clone", git_url, dirname])
        if rc != 0:
            sys.exit(rc)

# If we have the repo, we can fetch.
if os.path.exists(dirname):
    # Make sure we're up to date.
    rc = subprocess.call(["git", "fetch", "origin", refspec], cwd=dirname)
    if rc != 0:
        sys.exit(rc)

    # Extract the changeset.
    proc = subprocess.Popen(["git", "show", "FETCH_HEAD"], stdout=subprocess.PIPE, cwd=dirname)
    (stdout, stderr) = proc.communicate()
    if proc.returncode != 0:
        sys.exit(rc)

    # Save the info.
    (metadata, subject, message, issues, tokens) = extract_info(stdout)
else:
    # Generate the best we can.
    metadata = {}
    tokens = []
    issues = []
    if len(TOKENS) > 0:
        for match in re.finditer(TOKENRE, subject, re.IGNORECASE):
            tokens.append(match.group(2))
    for match in re.finditer(ISSUERE, subject):
        issues.append(match.group(2))
    for match in re.finditer(ISSUERE, message):
        issues.append(match.group(2))

# Dump extracted info.
print "subject:", subject
print "message:", message
print "issues:", issues
print "tokens:", tokens

# Find the user if available.
jira_user = "%s <%s>" % (author_name, author_email)
users = jira.search_users(author_email)
if len(users) == 1:
    jira_user = users[0].name
else:
    users = jira.search_users(author_name)
    if len(users) == 1:
        jira_user = users[0].name

# Verify all issues.
other_issues = {}
for issue in issues:
    other_issues[issue] = issues[:]
    other_issues[issue].remove(issue)
    jira.issue(issue)

# Add a comment if it's merged.
if event_type == "change-merged" and change_url:
    for issue in issues:
        # Append a very basic comment.
        body = "[~%s] has merged a [change|%s]." % (jira_user, change_url)

        if len(other_issues[issue]):
            # Append a comment with other related issues. This will make a link.
            body = body + "\nRelated issues: " + ",".join(other_issues[issue])

        # Add the comment to JIRA.
        comment = jira.add_comment(issue, body)

# Exit with okay if there are any tokens or issues.
if len(issues) > 0 or len(tokens) > 0:
    sys.exit(0)
else:
    sys.exit(1)
