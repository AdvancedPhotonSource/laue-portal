#!/usr/bin/env bash

full_name=$1

echo $full_name

repo=$(echo $full_name | awk -F '/' '{print $2}')

original_repo="gladier-client-template"


echo $repo
echo $original_repo

mv README.md HOW-TO.md
cp .github/README_STD.md README.md
sed -i "s/$original_repo/$repo/g" README.md

cp -r full_client $repo
mv $repo/full_client.py $repo/$repo\_client.py

rm -rf CITATION.cff
rm -rf .github