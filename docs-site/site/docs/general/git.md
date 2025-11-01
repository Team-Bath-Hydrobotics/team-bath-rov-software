This page documents how the team uses git.

The team adopts a hybrid strategy that mixes [github flow](https://docs.github.com/en/get-started/using-github/github-flow) and release branches.

## General development
Generally speaking as a developer to contribute you should do the following from the main branch
```
git fetch
git pull
git checkout -b feature/<name of your new branch>
```
Then make whatever changes you need, these should be small moduralised changes to make code reviews fast and to avoid large merge conflicts from divergent branches.
Once you are happy with your changes run
```
git add -A # adds all files
or 
git add <file to add> # adds a specific file
git commit -m "<some comment about the code>"
git push origin feature/<name-of-your-new-branch>
```
Then on github open a PR from <name-of-your-new-branch> to main
This should follow the [PR guidelines](pr.md).
Once your PR is approved merge it, run the following to keep your local main up to date
```
git checkout main
git pull origin main
```
Then delete your feature branch locally and remotely if no longer needed
```
git branch -d feature/<name-of-your-new-branch>
git push origin --delete feature/<name-of-your-new-branch>
```

## Release branches

When preparing a release, create a branch from main:
```
git checkout -b release/<version>
```
Only critical bug fixes and release preparation changes should go into the release branch.

Once ready, merge the release branch back into main, then tag it:
```
git checkout main
git merge release/<version>
git tag -a v<version> -m "Release <version>"
```
## Why we use release branches

Stability: The main branch always reflects the latest stable release. By having a separate release branch, we can finalize and test the release without blocking ongoing feature development.

Safe bug fixing: If a critical bug is found after the release branch is created, fixes can be applied directly to the release branch and then merged back into main, without disturbing features still in development.

Clear versioning: Release branches make it easier to track versions and apply tags for production or deployment.

Parallel development: We can continue working on new features in separate feature branches without affecting the release.