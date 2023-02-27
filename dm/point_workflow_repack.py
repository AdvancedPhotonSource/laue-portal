{
    'name'        : 'Process_Laue_Point_Repack',
    'owner'       : 'epix34id',
    'stages'      : {
        '01-Process-Point'  : {
            'command' : 'ssh epix34id@hpcs34 "/usr/bin/bash /clhome/EPIX34ID/dev/src/laue-gladier/scripts/launch_gladier_run.sh $experimentName $filePath"',
            'workingDir': '/clhome/EPIX34ID/dev/src/laue-gladier'
        },
        '02-Repack-Point'  : {
            'command' : 'ssh epix34id@hpcs34 "/usr/bin/bash /clhome/EPIX34ID/dev/src/laue-gladier/repackage/orthros_queue.sh $experimentName $filePath"',
            'workingDir': '/clhome/EPIX34ID/dev/src/laue-gladier'
        },
    },
    'description' : 'Workflow to trigger remote processing on Polaris via a gladier script.'
}
