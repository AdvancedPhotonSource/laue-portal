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
          <h1 className="card-title float-left">Scans</h1>
          <input type="text" placeholder="Search" className="input input-sm input-bordered float-right" />
        </div>
        <div className="divider"></div>
        <div className="overflow-scroll h-0 min-h-[90%]">
          <table className="table table-xs table-zebra">
            <thead>
              <tr>
                <th className="max-w-[25rem]" >Recon</th>
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
                    <td>
                      <a href={`/reconstruct?scan=${scan['#']}`} >
                        <button className="btn btn-square btn-neutral btn-sm">
                          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                        </button>
                      </a>
                    </td>
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
