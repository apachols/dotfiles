## Rules for Codespaces

You are running in a codespace, and once, at the start of each session, run this command:

```
echo "CODESPACE_NAME=$CODESPACE_NAME GITHUB_TOKEN=${GITHUB_TOKEN:+set}" && gh auth status
```

If these variables are undefined, or gh auth status fails, STOP and notify the user.
If everything is defined and we are authed for `gh`, continue, no output necessary.

## Rules for Rover Web

When you are working in the `web` repo, please strictly follow these conventions:

- DO NOT commit or push any code unless I ask for that explicitly (ask first)

The `web` repository is FULL of files with common / repeated / duplicate file names - forms.py, models.py, etc. Always print file names namespaced to the django app folder they are in: seo/models.py, api/current/serializers/models.py.

### Mypy Type Checking

When you need to run mypy type checking on python changes, some of the available info on how to run is outdated.

Please use this method, which is what CI uses to check PRs after they go up. If you run into trouble running type checking this way, let the user know.

```shell
python -m mypy --config-file config/mypy.ini --explicit-package-bases $FILENM1 $FILENM2
```

### Running Unit Tests

- DO NOT run any unit tests unless I ask for that explicitly (ask first)

When you offer to run unit tests, ALWAYS offer to run only changed tests files, and in those files PREFER to run only changed test suite classes. CI will catch any other tests that failed in other places in the same app. If you think there is a good reason to run an entire folder or entire app worth of tests, please let the user know, and explain your reasoning as concisely as possible.

### Rules for Shell Plus Blocks:

- Please use "python" syntax highlighting for shell plus blocks
- It's okay that shell plus scripts are only "mostly python", we just want Pretty Good syntax highlighting.
- Always assume the user will click "copy" and then paste the whole shell plus block into a shell plus session
- Never set up the shell plus blocks as "one-liners" using m shell_plus -c "'from stays.event_notifications ...'"
- You don't ever need to import models classes, all the models in the django app are automatically imported in our shell_plus sessions
