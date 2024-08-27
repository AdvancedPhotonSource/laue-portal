"use client";

import React, { useState, useEffect } from 'react'
import { useSearchParams } from 'next/navigation'


import FieldCkbx from "./checkbox";
import CollapseCard from "./collapse_card";
import FieldRow from "./field_row";
import ParamField from "./param_field";

const FIELD_SIZE = 500
const FIELD_SIZE_SM = 50


export default function Reconstruct() {
        const [params, setParams] = useState([])

    useEffect(() => {
        const fetchData = async () => {
            const response = await fetch('api/sample_params')
            const result = await response.json()
            setParams(result)
        }

        fetchData().catch((e) => {
            // handle the error as needed
            console.error('An error occurred while fetching the data: ', e)
        })
    }, [])


    return (
        <div className="space-y-4">
            <div className="card bg-base-100 shadow-xl">
                <div className="card-body">
                    <FieldRow>
                        <ParamField size='lg' fieldName={"Dataset"} defaultValue={params?.file?.path}/>
                    </FieldRow>

                    <FieldRow>
                        <ParamField size={'sm'} fieldName={"Frame Start"} defaultValue={params?.file?.range[0]}/>
                        <ParamField size={'sm'} fieldName={"Frame End"} defaultValue={params?.file?.range[1]}/>
                    </FieldRow>

                    <FieldRow>
                        <ParamField size={'sm'} fieldName={"X Start"} defaultValue={params?.file?.frame[0]}/>
                        <ParamField size={'sm'} fieldName={"X End"} defaultValue={params?.file?.frame[1]}/>
                        <ParamField size={'sm'} fieldName={"Y Start"} defaultValue={params?.file?.frame[2]}/>
                        <ParamField size={'sm'} fieldName={"Y End"} defaultValue={params?.file?.frame[3]}/>
                    </FieldRow>

                    <FieldRow>
                        <ParamField size={'sm'} fieldName={"Depth Start"} defaultValue={params?.geo?.source?.grid[0]}/>
                        <ParamField size={'sm'} fieldName={"Depth End"} defaultValue={params?.geo?.source?.grid[1]}/>
                        <ParamField size={'sm'} fieldName={"Resolution"} defaultValue={params?.geo?.source?.grid[2]}/>
                    </FieldRow>
                    <FieldRow>
                        <ParamField size={'lg'} fieldName={"Reconstruction Name"} />
                        <button className={`btn btn-neutral mt-auto w-[${'lg'}px]`}>Reconstruct</button>
                    </FieldRow>
                </div>
            </div>

            <CollapseCard title='Calibration'>
                <FieldRow>
                    <ParamField size={'md'} fieldName={"Cenx"} defaultValue={params?.geo?.mask?.focus?.cenx}/>
                    <ParamField size={'md'} fieldName={"Dist"} defaultValue={params?.geo?.mask?.focus?.dist}/>
                    <ParamField size={'md'} fieldName={"Cenz"} defaultValue={params?.geo?.mask?.focus?.cenz}/>
                </FieldRow>
                <FieldRow>
                    <ParamField size={'md'} fieldName={"AngleX"} defaultValue={params?.geo?.mask?.focus?.anglex}/>
                    <ParamField size={'md'} fieldName={"AngleY"} defaultValue={params?.geo?.mask?.focus?.angley}/>
                    <ParamField size={'md'} fieldName={"AngleZ"} defaultValue={params?.geo?.mask?.focus?.anglez}/>
                </FieldRow>
                <FieldRow>
                    <ParamField size={'md'} fieldName={"Shift"} defaultValue={params?.geo?.mask?.shift}/>
                </FieldRow>
            </CollapseCard>

            <CollapseCard title="Mask">
                <FieldRow>
                    <ParamField size={'lg'} fieldName={"Mask"} defaultValue={params?.geo?.mask?.path}/>
                    <FieldCkbx label={'Reversed'} defaultChecked={params?.geo?.mask?.path?.reversed}/>
                </FieldRow>
                <FieldRow>
                    <ParamField size={'sm'} fieldName={"BitSize 0"} defaultValue={params?.geo?.mask?.bitsizes[0]}/>
                    <ParamField size={'sm'} fieldName={"BitSize 1"} defaultValue={params?.geo?.mask?.bitsizes[1]}/>
                </FieldRow>
                <FieldRow>
                    <ParamField size={'lg'} fieldName={"Thickness"} defaultValue={params?.geo?.mask?.thickness}/>
                    <ParamField size={'lg'} fieldName={"Resolution"} defaultValue={params?.geo?.mask?.resolution}/>
                    <ParamField size={'lg'} fieldName={"Smoothness"} defaultValue={params?.geo?.mask?.smoothness}/>
                </FieldRow>
                <FieldRow>
                    <ParamField size={'lg'} fieldName={"Widening"} defaultValue={params?.geo?.mask?.widening}/>
                    <ParamField size={'lg'} fieldName={"Pad"} defaultValue={params?.geo?.mask?.pad}/>
                    <ParamField size={'lg'} fieldName={"Stretch"} defaultValue={params?.geo?.mask?.stretch}/>
                </FieldRow>
            </CollapseCard>

            <CollapseCard title="Motor Path">
                <FieldRow>
                    <ParamField size={'lg'} fieldName={"Step Size"} defaultValue={params?.geo?.scanner?.step}/>
                </FieldRow>

                <FieldRow>
                    <ParamField size={'sm'} fieldName={"Rot A"} defaultValue={params?.geo?.scanner?.rot[0]}/>
                    <ParamField size={'sm'} fieldName={"Rot B"} defaultValue={params?.geo?.scanner?.rot[1]}/>
                    <ParamField size={'sm'} fieldName={"Rot C"} defaultValue={params?.geo?.scanner?.rot[2]}/>
                </FieldRow>

                <FieldRow>
                    <ParamField size={'sm'} fieldName={"Ax X"} defaultValue={params?.geo?.scanner?.axis[0]}/>
                    <ParamField size={'sm'} fieldName={"Ax Y"} defaultValue={params?.geo?.scanner?.axis[1]}/>
                    <ParamField size={'sm'} fieldName={"Ax Z"} defaultValue={params?.geo?.scanner?.axis[2]}/>
                </FieldRow>
            </CollapseCard>

            <CollapseCard title="Detector">
                <FieldRow>
                    <ParamField size={'sm'} fieldName={"Pixels X"} defaultValue={params?.geo?.detector?.shape[0]}/>
                    <ParamField size={'sm'} fieldName={"Pixels Y"} defaultValue={params?.geo?.detector?.shape[1]}/>
                </FieldRow>

                <FieldRow>
                    <ParamField size={'sm'} fieldName={"Size X (mm)"} defaultValue={params?.geo?.detector?.size[0]}/>
                    <ParamField size={'sm'} fieldName={"Size Y (mm)"} defaultValue={params?.geo?.detector?.size[1]}/>
                </FieldRow>

                <FieldRow>
                    <ParamField size={'sm'} fieldName={"Rot A"} defaultValue={params?.geo?.detector?.rot[0]}/>
                    <ParamField size={'sm'} fieldName={"Rot B"} defaultValue={params?.geo?.detector?.rot[1]}/>
                    <ParamField size={'sm'} fieldName={"Rot C"} defaultValue={params?.geo?.detector?.rot[2]}/>
                </FieldRow>

                <FieldRow>
                    <ParamField size={'sm'} fieldName={"Pos X"} defaultValue={params?.geo?.detector?.pos[0]}/>
                    <ParamField size={'sm'} fieldName={"Pos Y"} defaultValue={params?.geo?.detector?.pos[1]}/>
                    <ParamField size={'sm'} fieldName={"Pos Z"} defaultValue={params?.geo?.detector?.pos[2]}/>
                </FieldRow>
            </CollapseCard>
            <CollapseCard title="Algorithm Parameters">
                <FieldRow>
                    <ParamField size={'sm'} fieldName={"Iters"} defaultValue={params?.file?.range[0]}/>
                </FieldRow>

                <FieldRow>
                    <ParamField size={'sm'} fieldName={"Pos Method"} defaultValue={params?.algo?.pos?.method}/>
                    <ParamField size={'sm'} fieldName={"Pos Regpar"} defaultValue={params?.algo?.pos?.regpar}/>
                    <ParamField size={'sm'} fieldName={"Pos Init"} defaultValue={params?.algo?.pos?.init}/>
                </FieldRow>

                <div className="divider"></div>
                <FieldRow>
                    <FieldCkbx label={"Enable Sigrecon"} defaultChecked={params?.algo?.sig}/>
                </FieldRow>

                <FieldRow>
                    <ParamField size={'sm'} fieldName={"Sig Method"} defaultValue={params?.algo?.sig?.method}/>
                    <ParamField size={'sm'} fieldName={"Sig Order"} defaultValue={params?.algo?.sig?.order}/>
                    <ParamField size={'sm'} fieldName={"Sig Scale"} defaultValue={params?.algo?.sig?.scale}/>
                </FieldRow>

                <FieldRow>
                    <ParamField size={'sm'} fieldName={"Sig Maxsize"} defaultValue={params?.algo?.sig?.init?.maxsize}/>
                    <ParamField size={'sm'} fieldName={"Sig Avgsize"} defaultValue={params?.algo?.sig?.init?.avgsize}/>
                    <ParamField size={'sm'} fieldName={"Sig Atol"} defaultValue={params?.algo?.sig?.init?.atol}/>
                </FieldRow>

                <div className="divider"></div>
                <FieldRow>
                    <FieldCkbx label="Enable Enerecon" defaultChecked={params?.algo?.ene?.recon} />
                    <FieldCkbx label="Exact Enerecon" defaultChecked={params?.algo?.ene?.exact} />
                </FieldRow>

                <FieldRow>
                    <ParamField size={'sm'} fieldName={"ene method"} defaultValue={params?.algo?.ene?.method}/>
                </FieldRow>

                <FieldRow>
                    <ParamField size={'sm'} fieldName={"ene min"} defaultValue={params?.algo?.ene?.range[0]}/>
                    <ParamField size={'sm'} fieldName={"ene max"} defaultValue={params?.algo?.ene?.range[1]}/>
                    <ParamField size={'sm'} fieldName={"ene step"} defaultValue={params?.algo?.ene?.range[2]}/>
                </FieldRow>
            </CollapseCard>


        </div>
    )
}