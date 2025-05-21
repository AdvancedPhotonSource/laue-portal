{
    'name'        : 'Process_Laue_Point',
    'owner'       : 'epix34id',
    'stages'      : {
        '01-Process-Point'  : {
            'command' : 'ssh epix34id@hpcs34 "/usr/bin/bash /clhome/EPIX34ID/dev/src/laue-gladier/scripts/launch_gladier_run.sh $experimentName $filePath"',
            'workingDir': '/clhome/EPIX34ID/dev/src/laue-gladier'
        },
    },
    'description' : 'Workflow to trigger remote processing on Polaris via a gladier script.'
}
