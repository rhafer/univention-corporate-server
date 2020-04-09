GitLab-CI
=========

- [x] Add `ucslint`
- [x] Include `/var/lib/apt/lists/` in Docker images to speed up build
- [ ] Evaluate [Inter-package-dependencies](https://git.knut.univention.de/phahn/test/-/blob/master/BUILD.md)
- [ ] Store `*.deb` in [RepRepRo](http://10.200.18.180/debian/) - see [git-feature-branch-builder](https://git.knut.univention.de/univention/internal/git-feature-branch-builder/-/blob/master/build)
- [ ] Store `*.deb` in [Debian Package manager MVC](https://gitlab.com/gitlab-org/gitlab/-/issues/5835#note_303037719)
- [x] Store `*.deb` in [Aptly](https://www.aptly.info/)
- [ ] Add pipeline to publish documentation to [docs.software-univentionunivention.de](https://git.knut.univention.de/univention/docs.univention.de)
- [x] Switch back to [generated pipeline](https://docs.gitlab.com/ee/ci/yaml/#trigger-child-pipeline-with-generated-configuration-file)
- [ ] Reproducible build - see [Debian pipeline](https://salsa.debian.org/salsa-ci-team/pipeline/)
- [ ] Show package diff
