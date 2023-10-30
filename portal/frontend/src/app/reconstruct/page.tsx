import FieldCkbx from "./checkbox";
import CollapseCard from "./collapse_card";
import FieldRow from "./field_row";
import ParamField from "./param_field";

const FIELD_SIZE = 500
const FIELD_SIZE_SM = 50


export default function Reconstruct() {



    return (
        <div className="space-y-4">
            <div className="card bg-base-100 shadow-xl">
                <div className="card-body">
                    <FieldRow>
                        <ParamField size='lg' fieldName={"Dataset"} />
                        <ParamField size='lg' fieldName={"Input Layers"} />
                        <ParamField size='lg' fieldName={"Depth Range"} />
                    </FieldRow>
                    <FieldRow>
                        <ParamField size='lg' fieldName={"Threshold"} />
                        <ParamField size='lg' fieldName={"Pixel Range"} />
                    </FieldRow>

                    <FieldRow>
                        <ParamField size={'sm'} fieldName={"Depth Start"} />
                        <ParamField size={'sm'} fieldName={"Depth End"} />
                        <ParamField size={'sm'} fieldName={"Resolution"} />
                    </FieldRow>
                    <FieldRow>
                        <ParamField size={'lg'} fieldName={"Reconstruction Name"} />
                        <button className={`btn btn-primary mt-auto w-[${'lg'}px]`}>Reconstruct</button>
                    </FieldRow>
                </div>
            </div>

            <CollapseCard title='Calibration'>
                <FieldRow>
                    <ParamField size={'md'} fieldName={"Cenx"} />
                    <ParamField size={'md'} fieldName={"Dist"} />
                    <ParamField size={'md'} fieldName={"Cenz"} />
                </FieldRow>
                <FieldRow>
                    <ParamField size={'md'} fieldName={"AngleX"} />
                    <ParamField size={'md'} fieldName={"AngleY"} />
                    <ParamField size={'md'} fieldName={"AngleZ"} />
                </FieldRow>
                <FieldRow>
                    <ParamField size={'md'} fieldName={"Shift"} />
                </FieldRow>
            </CollapseCard>

            <CollapseCard title="Mask">
                <FieldRow>
                    <ParamField size={'lg'} fieldName={"Mask"} />
                    <FieldCkbx label={'Reversed'} />
                </FieldRow>
                <FieldRow>
                    <ParamField size={'sm'} fieldName={"BitSize 0"} />
                    <ParamField size={'sm'} fieldName={"BitSize 1"} />
                </FieldRow>
                <FieldRow>
                    <ParamField size={'lg'} fieldName={"Thickness"} />
                    <ParamField size={'lg'} fieldName={"Resolution"} />
                    <ParamField size={'lg'} fieldName={"Smoothness"} />
                </FieldRow>
                <FieldRow>
                    <ParamField size={'lg'} fieldName={"Widening"} />
                    <ParamField size={'lg'} fieldName={"Pad"} />
                    <ParamField size={'lg'} fieldName={"Stretch"} />
                </FieldRow>
            </CollapseCard>

            <CollapseCard title="Motor Path">
                <FieldRow>
                    <ParamField size={'lg'} fieldName={"Step Size"} />
                </FieldRow>

                <FieldRow>
                    <ParamField size={'sm'} fieldName={"Rot A"} />
                    <ParamField size={'sm'} fieldName={"Rot B"} />
                    <ParamField size={'sm'} fieldName={"Rot C"} />
                </FieldRow>

                <FieldRow>
                    <ParamField size={'sm'} fieldName={"Ax X"} />
                    <ParamField size={'sm'} fieldName={"Ax Y"} />
                    <ParamField size={'sm'} fieldName={"Ax Z"} />
                </FieldRow>
            </CollapseCard>

            <CollapseCard title="Detector">
                <FieldRow>
                    <ParamField size={'sm'} fieldName={"Pixels X"} />
                    <ParamField size={'sm'} fieldName={"Pixels Y"} />
                </FieldRow>

                <FieldRow>
                    <ParamField size={'sm'} fieldName={"Size X (mm)"} />
                    <ParamField size={'sm'} fieldName={"Size Y (mm)"} />
                </FieldRow>

                <FieldRow>
                    <ParamField size={'sm'} fieldName={"Rot A"} />
                    <ParamField size={'sm'} fieldName={"Rot B"} />
                    <ParamField size={'sm'} fieldName={"Rot C"} />
                </FieldRow>

                <FieldRow>
                    <ParamField size={'sm'} fieldName={"Pos X"} />
                    <ParamField size={'sm'} fieldName={"Pos Y"} />
                    <ParamField size={'sm'} fieldName={"Pos Z"} />
                </FieldRow>
            </CollapseCard>
            <CollapseCard title="Algorithm Parameters">
                <FieldRow>
                    <ParamField size={'sm'} fieldName={"iters"} />
                </FieldRow>

                <FieldRow>
                    <ParamField size={'sm'} fieldName={"pos method"} />
                    <ParamField size={'sm'} fieldName={"pos regpar"} />
                    <ParamField size={'sm'} fieldName={"pos init"} />
                </FieldRow>

                <div className="divider"></div>
                <FieldRow>
                    <FieldCkbx label={"Enable Sigrecon"} />
                </FieldRow>

                <FieldRow>
                    <ParamField size={'sm'} fieldName={"sig method"} />
                    <ParamField size={'sm'} fieldName={"sig order"} />
                    <ParamField size={'sm'} fieldName={"sig scale"} />
                </FieldRow>

                <FieldRow>
                    <ParamField size={'sm'} fieldName={"sig maxsize"} />
                    <ParamField size={'sm'} fieldName={"sig avgsize"} />
                    <ParamField size={'sm'} fieldName={"sig atol"} />
                </FieldRow>

                <div className="divider"></div>
                <FieldRow>
                    <FieldCkbx label="Enable Enerecon"></FieldCkbx>
                    <FieldCkbx label="Exact Enerecon"></FieldCkbx>
                </FieldRow>

                <FieldRow>
                    <ParamField size={'sm'} fieldName={"ene method"} />
                </FieldRow>
            
                <FieldRow>
                    <ParamField size={'sm'} fieldName={"ene min"} />
                    <ParamField size={'sm'} fieldName={"ene max"} />
                    <ParamField size={'sm'} fieldName={"ene step"} />
                </FieldRow>
            </CollapseCard>


        </div>
    )
}