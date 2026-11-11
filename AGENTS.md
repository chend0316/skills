# Repository instructions

Store skills under `skills/<name>/` and keep each skill self-contained. Use relative paths in skill documentation.

Use the following identity for every commit in this repository, including both the author and committer.

- Name `chend0316`
- Email `chendong0316@163.com`

After modifying code-map scripts or HTML assets, run `python3 -m unittest discover -s skills/code-map/scripts -v`. Node.js is required for the interaction checks.

Publish versions by creating and pushing Git tags. Do not create GitHub Release pages unless the user explicitly requests one.
