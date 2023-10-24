"use client";

import { useEffect, useState } from "react";

export default function Scans() {

  const [scans, setScans] = useState([]);

  useEffect(() => {
    const fetchata = async () => {

      const response = await fetch(
        'api/sample_scans');
      const data = await response.json();
      
      setScans(data)
    }
    // Call the function
    fetchata();
  }, []);



  return (
    <div>
      <div className="flow-root">
        <h1 className="card-title float-left">Scans</h1>
        <input type="text" placeholder="Search" className="input input-sm input-bordered float-right" />
      </div>
      <div className="divider"></div>
      <table className="table table-pin-cols table-zebra">
        <thead>
          <tr>
            {
              scans.headers?.map((header, key) =>
              <th key={key}>{header}</th>
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
  )
}
