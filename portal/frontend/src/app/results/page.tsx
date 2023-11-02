"use client";

import { useEffect, useState } from "react";

export default function Scans() {

  const [scans, setScans] = useState([]);

  useEffect(() => {
    const fetchata = async () => {

      const response = await fetch('api/sample_scans');
      const data = await response.json();
      
      setScans(data)
    }
    // Call the function
    fetchata();
  }, []);



  return (
    <div className="card bg-base-100 shadow-xl h-0 min-h-[100%]">
      <div className="card-body">
        <div className="">
          <h1 className="card-title float-left">Results</h1>
          <input type="text" placeholder="Search" className="input input-sm input-bordered float-right" />
        </div>
        <div className="divider"></div>
        <div className="overflow-scroll h-0 min-h-[90%]">
          <table className="table table-xs table-zebra">
            <thead>
              <tr>
                {
                  scans.headers?.map((header, key) =>
                    <th className="max-w-[25rem]" key={key}>{header}</th>
                  )
                }
              </tr>
            </thead>
            <tbody>
              {
                scans.data?.map((scan, key) =>
                  <tr key={key}>
                    {
                      scans.headers?.map((header, key) =>
                        <td key={key}>{scan[header]}</td>
                      )
                    }

                  </tr>
                )
              }

            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
