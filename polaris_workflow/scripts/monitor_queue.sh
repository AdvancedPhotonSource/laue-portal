time=0
while true
do
   pretty_time=`printf %05d $time`
   qstat -f -F json demand > $1/${pretty_time}.json
   time=$((time + 10))
   echo ${pretty_time}
   sleep 10
done