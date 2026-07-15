import os
import re
import shutil
import tempfile
import uuid
import zipfile

import git


def _clean_git_error(e: git.GitCommandError) -> str:
    stderr = (e.stderr or "").strip()
    relevant_lines = [
        line.strip().lstrip("'\"")
        for line in stderr.splitlines()
        if line.strip().startswith(("remote:", "fatal:"))
    ]
    if relevant_lines:
        return " ".join(relevant_lines)
    return "git clone failed — check that the URL points to a public repository."


def clone_github_repo(url: str) -> tuple[str, str]:
    repo_name = url.rstrip("/").split("/")[-1].replace(".git", "")
    repo_id = re.sub(r"[^a-z0-9]", "-", repo_name.lower()) + "-" + str(uuid.uuid4())[:6]
    tmp_dir = tempfile.mkdtemp()
    try:
        git.Repo.clone_from(url, tmp_dir)
    except git.GitCommandError as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise ValueError(_clean_git_error(e)) from e
    return tmp_dir, repo_id


def _safe_extract(z: zipfile.ZipFile, dest_dir: str) -> None:
    dest_dir = os.path.realpath(dest_dir)
    for member in z.namelist():
        target = os.path.realpath(os.path.join(dest_dir, member))
        if not (target == dest_dir or target.startswith(dest_dir + os.sep)):
            raise ValueError(f"Unsafe path in zip archive: {member}")
    z.extractall(dest_dir)


def extract_zip(zip_path: str) -> tuple[str, str]:
    tmp_dir = tempfile.mkdtemp()
    with zipfile.ZipFile(zip_path, "r") as z:
        _safe_extract(z, tmp_dir)
    repo_id = "upload-" + str(uuid.uuid4())[:6]
    return tmp_dir, repo_id
