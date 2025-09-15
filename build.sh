#!/bin/bash

if [[ $# != 3 ]]; then
    echo Usage: $0 root-dir branch-name patches-dir 1>&2
    exit 1
fi

REPO_URL=https://github.com/JetBrains/intellij-community.git
ROOT_DIR=$1
BRANCH_NAME=$2
RELEASE=$(echo $BRANCH_NAME | awk -F '[/.]' '{ print $2 }')
PATCHES_DIR=$3

set -ex

if [[ ! -d $ROOT_DIR ]]; then
    git clone $REPO_URL $ROOT_DIR
    cd $ROOT_DIR
    ./getPlugins.sh
fi

cd $ROOT_DIR/android
git reset --hard
git fetch
git checkout $BRANCH_NAME

cd $ROOT_DIR
git reset --hard
git fetch
git checkout $BRANCH_NAME

cd $ROOT_DIR
for patch in $PATCHES_DIR/*.patch; do
    alt_patch=$patch.$RELEASE
    if [[ -e $alt_patch ]]; then
	patch=$alt_patch
    fi
    git apply $patch
done

cd $ROOT_DIR
rm -rf out
./installers.cmd
