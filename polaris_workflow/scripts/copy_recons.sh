echo "Copying from $1 to $2"
mkdir -p $2
find $1 -type f -print0 | xargs -0 cp -t $2
