# Repository instructions

Store skills under `skills/<name>/` and keep each skill self-contained. Use relative paths in skill documentation.

When adding, renaming, or changing a skill's capabilities, keep the README skill catalog, requirements, usage examples, and local verification instructions in sync.

Use the following identity for every commit in this repository, including both the author and committer.

- Name `chend0316`
- Email `chendong0316@163.com`

After modifying code-map scripts or HTML assets, run `python3 -m unittest discover -s skills/code-map/scripts -v`. Node.js is required for the interaction checks; confirm they execute rather than skip.

After modifying harmony-memory-diagnostics scripts, run `python3 -m unittest discover -s skills/harmony-memory-diagnostics/scripts -v`. These tests are offline and must not contact a device or change an application. They do not replace real-device validation of the diagnostic workflow.

Do not create GitHub Release pages unless the user explicitly requests one.
