from laueanalysis.reconstruct import reconstruct
from pathlib import Path

def main():
    """
    Python script to run the reconstruction process based on the parameters
    from 'sandbox/run_reconstructBP_local.sh'.
    """
    # Define variables from the shell script
    input_file = "/net/s34data/export/s34data1/LauePortal/DS_test/Si-wire_7.h5"
    output_file_base = "/net/s34data/export/s34data1/LauePortal/MRD_source/laue-portal/output_cpu/Si-wire_7_"
    geo_file = "/net/s34data/export/s34data1/LauePortal/DS_test/geoN_2023-04-06_03-07-11_cor6.xml"
    depth_start = -10
    depth_end = 10
    resolution = 0.5
    verbose = 1
    memory_use = 50000
    percent_to_process = 100.0
    n_threads = 35
    detector = 0

    # Create output directory if it doesn't exist
    output_dir = Path(output_file_base).parent
    output_dir.mkdir(exist_ok=True)

    # Call the reconstruct function
    # The shell script defined FIRST_IMAGE and LAST_IMAGE but did not use them in the call.
    # The 'reconstruct' function's 'image_range' parameter is therefore omitted.
    # The shell script also defined WIRE_EDGES but did not use it.
    # We rely on the default 'wire_edge' parameter in the 'reconstruct' function.
    result = reconstruct(
        input_file=input_file,
        output_file=output_file_base,
        geometry_file=geo_file,
        depth_range=(depth_start, depth_end),
        resolution=resolution,
        verbose=verbose,
        percent_brightest=percent_to_process,
        memory_limit_mb=memory_use,
        detector_number=detector,
        num_threads=n_threads,
    )

    # Print the result
    if result.success:
        print("Reconstruction successful!")
        print("Log:")
        print(result.log)
        print("\nOutput files created:")
        for f in result.output_files:
            print(f"- {f}")
    else:
        print("Reconstruction failed.")
        print(f"Error: {result.error}")
        if result.log:
            print("\nLog:")
            print(result.log)

    print(f"\nCommand executed:\n{result.command}")
    print(f"Return code: {result.return_code}")

if __name__ == "__main__":
    main()
 