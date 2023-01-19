# gladier-client-template

This is a step-by-step guide to creating a fully automated experiment with the use of [Globus](https://www.globus.org) tools via the [Gladier](https://github.com/globus-gladier/gladier) automation library. Full documentation can be found at [Gladier Read the Docs](https://gladier.readthedocs.io/); see also [FuncX](https://www.funcx.org) for information about the remote execution mechanisms used in our automation. 

## Your Journey starts here ...
### If you choose to accept the challenge.
------------------------------
Hello traveler. Welcome to this guide to the _Globus Architecture for Data-Intensive Experimental Research_, in short, GLADIER--a library designed to facilitate the authoring of **flows**, sequences of **actions** (e.g., running a program, transferring data, publishing data) associated with the processing of data from experimental facilities. 

This step-by-step guide to the use of Gladier and associated tools will prepare you to author and run multi-step flows.

> A `flow` is a sequence of actions that are to be performed. This sequence is defined by a `recipe` (also known as a *flow-definition*). A flow-definition contains all information necessary to execute each step of the flow, including:<br>
    * **What**: The actions to be executed <br>
    * **Where**: Where each action is to be executed <br>
    * **When**: The order in which the actions are executed

A **client** is the code that defines all necessary information to run a flow. To simplify understanding, we work here with three example flows that each comprise a single step representing three types of operation:

* The **Process** flow, at `simple_clients/example_client_process.py`, runs a program at a specified location
* The **Transfer** flow, at `simple_clients/example_client_transfer.py`, transfers data from one location to another
* The **Publish** flow, at `simple_clients/example_client_publish.py`, loads data and metadata to a catalog

## Installing Gladier

For full automation of an experiment, there is infrastructure setup that cannot be ignored. This is usually done once, after which you can focus on tool development. 

We advise creating a new Python environment to run this tutorial. For simplicity, we use [miniconda](https://docs.conda.io/en/latest/miniconda.html):

    conda create -n gladier-test python pip
    conda activate gladier-test
    pip install gladier

## First run on a Gladier Client

Our first example, **Process** (`simple_clients/example_client_process.py`) defines a single step flow that executes a Python function at a specified remote location.

   ./simple_clients/example_client_process.py

In order to execute a remote function (the equivalent of a `lambda`) we use the funcX service to register, retrieve, and execute functions. The service requires that a small instance client be deployed at the "processing" machine. We have a client running on one of our example machines. The location of this client is defined by:

    'funcx_endpoint_compute': '4b116d3c-1703-4f8f-9f6f-39921e5864df'

> Running the **Funcx Client** on a computer gives a flow the ability to `send` functions to be executed on that computer. (This computer may be a remote cluster of cloud, or alternatively the computer on which the flow client executes: funcX runs the same in each case.) As we explore later, different parts of the flow can be executed on different computers by providing different `funcx_endpoint_compute` value for each part.

The **Process** flow runs the function defined by `tools/simple_funcx_tool.py` and imported into the client as `SimpleTool`. Gladier automatically checks for updates on the function definition and registers or re-registers (if the local function definition has changed) with the funcx service. The UUID of this function is automatically populated in the flow definition. 

Before the execution the `input` variables need to be defined to contain **all** information necessary for the flow. In our case, that information includes two input parameters expected by `SimpleTool` (`name` and `wfile`) and the location of the computer where the function is to execute, `funcx_endpoint_compute`.

    flow_input = {
        'input': {
            'name': args.name, 
            'wfile' : '/test/test.txt',

            # funcX tutorial endpoint
            'funcx_endpoint_compute': '4b116d3c-1703-4f8f-9f6f-39921e5864df',
        }
    }

At the next step in the execution, Gladier looks for changes in the Tool definition and tool sequence, then takes care of creating the flow definition and (re-)registering it with the globus automate service. Once a flow is created, it can be accessed in the globus webApp like the link below.

    Flow created with ID: ddb9d6be-d48f-40df-a663-6bcc6db1bb76                                                              https://app.globus.org/flows/ddb9d6be-d48f-40df-a663-6bcc6db1bb76 

Once a flow is `.run()` it generates a unique UUID for that particular set of flow definition and payload. The log can also be accessed at the webApp:

    Run started with ID: 6fa0969a-2778-4f7f-95d5-d365e89aca32                                                               https://app.globus.org/runs/6fa0969a-2778-4f7f-95d5-d365e89aca32 

Running the client again will not register a new flow with the globus service but will generate a new run instance.

### Best Practices:

* We suggest keeping the client `def` outsite of the `__main__` function of the python file. Then creating an instance at `__main__` and using `.run()`.
* Each tool in the flow have separate `required_inputs` that need to be included in the initial payload. 
* The `SimpleTool` and its driving function `simple_funcx_function` are separated into a `tools` folder in a single file. We advise to create one python file per "action" in the flows. This makes development and debugging and tracing errors much simpler.
* The `example_client.py` itself also is separated from the other clients in the folder and only contain one `GladierBaseClient`. This prevents instances being created with the 'wrong' flow definition or common mistakes on 'what is running'.


## Creating a flow with Transfer

Our second example can be found at `simple_clients/example_client_transfer.py`. It transfer a file from our remote server into your workstation. 
In order to allow for transfer, the first step is to introduce the workstation in the the creates and executes another 1-step flow. This flow will create a file on the local filesystem and send it to our remote server.

> Before executing this file, please create **Globus Endpoint** at your machine following the instructions at: `https://www.globus.org/globus-connect-personal` after the installation you will receive a UUID of your machine (which is now a `storage endpoint`) and update line 38 with your own uuid.

    local_endpoint_id = 'cde22510-5de7-11ec-9b5c-f9dfb1abb183' 

Now go ahead and execute the code.

    ./simple_clients/example_client_transfer.py

Notice how in this case the `input` is different. Now defining the `source_id`, `source_path`, `remote_id`,`remote_path`.  

    flow_input = {
        'input': {
            #local server information
            'simple_transfer_source_endpoint_id': local_endpoint_id,
            'simple_transfer_source_path': os.path.expanduser(args.dir),

            #remote server information
            'simple_transfer_destination_endpoint_id':'ef4203ca-6510-466c-9bff-a5d2cc316673',
            'simple_transfer_destination_path':'/demo/animals/',
        }
    }

You can see the files transfered on the [globus app](https://app.globus.org/file-manager), the code will also print a direct link showing both your endpoint and the remote one.

## Creating a flow with Publish

Our Third 1-step example can be found at `simple_clients/example_client_publish.py`. It do a simple operation of publishing some data into a globus index.

As before, it requires the setup of a `globus index` and how to visualize it.

    pip install globus-search-cli
    globus-search login
    globus-search index create example-index gladier-example-index

The result is a new search index on the globus-search database which will serve as a "repository" for the flow data.

    {  "@datatype": "GSearchIndex",
       "@version": "2017-09-01",
       "creation_date": "2022-04-27 21:04:30",
       "description": "gladier-example-index",
       "display_name": "example-index",
       "id": "563c3d98-6fa8-4ef5-83e2-0f378efe0a5f",
       ...
    }    

The search index id `563c3d98-6fa8-4ef5-83e2-0f378efe0a5f` will be used so the flow knows where to send metadata too.

To execute our simple publish client

   ./example_client/example_client_publish.py

To check if the data went to the index try this check https://acdc.alcf.anl.gov/globus-tutorial/563c3d98-6fa8-4ef5-83e2-0f378efe0a5f

## Stop!

At this point. You have the tools to create 1-step flows. We suggest you play with the examples and create your own python functions. Some ideas:

* Create your own funcx endpoint and try executing functions at your own machine. One simple way to see where is being executed is to create a file at your desktop.
* Now try transfering this file into our remote server
* And retrieving the information of this file and adding to your search index.
* Try downloading the file from the globusApp

## Your journey continues here
### You shall pass!

Most flows will be a combination of the steps above. Our next step is to merge all of then into a single flow.
For simplicity, we start a new client in `/full_client` with a new set of `/tools`. This time, we will focus on how to execute it all at once.

The idea is to create the infrastructure based on the simple_examples and expand it into a flow with:

* Transfer
* Funcx 
* Funcx 
* Publish

### Defining the correct payload

As you noticed above, each 1-step flow have different payloads. Now, all the `input` variables need to be defined at once.

> **Best practice** the name of each variable on the payload should match the input name of the variables on the funcx functions. Keeping then separate and well commented on the client makes debugging much faster for you and others.

### Using flow modifiers

Auto creating the flow definitions is great but sometimes you may want to change variables like "Timeouts" or which endpoint will execute each function

> **Best practice** for machines that require `queieng` we define two endpoints `funcx_endpoint_non_compute` at the head node and `funcx_endpoint_compute` at the queued nodes. Note that since they live in the machine, they share the same `globus_endpoint` and therefore can access the same files. You can use the `non_compute` endpoint for funcx functions which do not require lots of compute power.

### Importing external functions

Functions may already been created by you or others. You can importa a `GladierBaseTool` from a different package and include it directly into your flow. Gladier will take care of registering the funcx definition with your username.

> **Tip** [Gladier-Tools](https://www.github.com/globus-gladier/gladier-tools) already have lots of tools for posix, transfer and publish operations. In special, `Publish` is very useful to automatically create and ingest metadata based on your experiment. Lets explore it further below.

### gladier_tools.Publish


### Single Instance client

Our flow now is defined on an executable file and can be integrated with any CLI based execution method. 

### Creating an event based client


Since our Single Instance Client defines a `run_flow` function that only needs a set defined set of variables to run.
We can create a FileWatcher that creates this payload whenever a new file is created/modified.
The watcher itself does not carry any information about the flow.

## You shall not pass!!

Lets explore what was covered on the example before. 
