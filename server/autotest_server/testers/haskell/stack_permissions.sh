echo "allow-different-user: true" >> $STACK_ROOT/config.yaml
echo "recommend-stack-upgrade: false" >> $STACK_ROOT/config.yaml
chmod a+w $STACK_ROOT/stack.sqlite3.pantry-write-lock
chmod a+w $STACK_ROOT/global-project/.stack-work/stack.sqlite3.pantry-write-lock
chmod a+w $STACK_ROOT/pantry/pantry.sqlite3.pantry-write-lock