# Laue-Gladier

Repository for automated data processing and triggering of laue-parallel and cold processing.

## Project Structure

* `dm` contains workflows for the APS Data Management system which monitors files as the detector writes them to system and triggers the downstream processing. 
* `funcx_launch` contains the funcx endpoint and launch scripts to be staged on the Polaris AMN or login node. This endpoint is used to launch jobs and monitor the queue. 
* `laue_client` contains the gladier workflow triggered by the DM workflow and calling the funcx endpoint. This includes the workflow to handle data transfer and triggering of the job on Polaris. 
* `scripts` includes various scripts including the primary script bridging dm and galdier, a detector simulator script, and some reference scripts to work with the DM system.

## Setup and Launch

Setup:

1. A DM experiment must be created with a DAQ monitoring the filesystem and hooked up to the point workflow. 
2. On Polaris, a funcx endpoint must be running, with access to the PBS queue. 
3. The glaider workflow must be configured to point to the correct directories, funcx endpoint ID, and globus EP IDs. 

Launch:
With this in place, processing will be automatically launched by placing data in a folder that the DAQ is monitoring. For debug, launch can be manually triggered via the `scripts/launch_gladier_run.sh` script if the data has already been staged in Voyager. 