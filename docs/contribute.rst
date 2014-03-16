=================================
Contributing to Onitu
=================================

Onitu is an opensource project, all of our codebase is available on Github and we would be very happy to include fixes or features from the comunity.
Here are some guidelines on what to look out for if you are hacking the code or having issues.

Reporting issues
================

When you encounter an issue with Onitu we'dd love to here about it. Not that we particularly like having problems with the codebase, but its better to fix them than to leave them in there.
If you submit a bug report please include all the information available to you, here are some things you can do:
- If the problem is reproductible you can restart Onitu in debugging mode.
- Onitu generate logging output, this is very usefull to us.
- Try to simplify the things you are doing until getting a minimal set of actions reproducing the problem.

.. _tests:

Running the tests
=================

If you developed a new feature or simply want to try out an instalation of Onitu you can run the unit tests. For this you will need to install the requirements for the testing framework, this can easily be done using:
- pip install -r requirements_dev.txt

- py.test
- tox
- env vars

Good practices with Git
=======================

In order to maintain the project while including contributions from the opensource comunity we need to have some rules in place. This is especialy true with regard to the use of Git.
When developing new features this should always be done on feature branches that are dedicated to that particular feature. Once the feature is ready, the feature branch should be rebased on the current develop branch before doing a pull request. The maintainers of the develop branch will then review the pull request and merge it into develop when its ready. They might ask you to do some changes beforehand. You should never merge master onto your feature branch, instead always use rebase on local code.

Coding style
============

The code you contribute to the project should respect the guidelines defined in :pep:`008`, you can use a tool such as flake8 to check if this is the case. In case you're wondering: we use four spaces indentation.
Please take those rules into account, we aim to have a clean codebase and codestyle is a big part of that. Your code will be checked when we consider your pull requests.
