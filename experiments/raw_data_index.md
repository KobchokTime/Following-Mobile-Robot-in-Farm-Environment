# Raw-data index

Inventory status: incomplete. This cloud environment cannot access the user's Windows backup
or robot-side storage, and no backup directory is mounted under `/workspace`.

The mounted workspace was searched for `.avi`, `.mp4`, `.mov`, `.mkv`, `.bag`, `.db3`, and
`.mcap` files and rosbag2 `metadata.yaml` files. No matching assets were present, so there are
no paths, sizes, hashes, or contents to record yet. This is not an inventory of files on the
Windows machine or robot.

## Storage proposal

- Use a private object-storage bucket for raw robot recordings when access should remain limited
  to the project team. Keep an index entry here with the object key, size, SHA-256, and a short
  description.
- A GitHub Release can hold a small, shareable dataset when the repository's visibility and
  release access match the data's access requirements.
- Keep video and bag binaries out of Git. Publish a sanitized sample separately if a public
  research artifact is needed.

To complete the inventory, mount or provide the Windows backup directory and repeat the same
file listing and hashing there.
