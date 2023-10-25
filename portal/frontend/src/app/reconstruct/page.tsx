import ParamField from "./param_field";
import ParamField2 from "./param_field_2";

export default function Reconstruct() {
    return (
        <div className="space-y-4">
            <div className="card bg-base-100 shadow-xl">
                <div className="card-body">
                    <ParamField2 size={0.5} fieldName={"Dataset"} />
                    <ParamField2 size={0.5} fieldName={"Input Layers"} />
                    <ParamField2 size={0.5} fieldName={"Threshold"} />
                    <ParamField2 size={0.5} fieldName={"Pixel Range"} />
                    <ParamField2 size={0.5} fieldName={"Reconstruction Name"} />
                    <ParamField2 size={0.5} fieldName={"Depth Range"} />
                </div>
            </div>
            <div className="collapse shadow-xl bg-base-100 collapse-plus">
                <input type="checkbox" />
                <div className="collapse-title text-xl font-medium bg-100 ">
                    Calibration
                </div>
                <div className="collapse-content">
                    <div className="flex flex-row gap-x-5">
                        <ParamField2 size={0.5} fieldName={"cenx"} />
                        <ParamField2 size={0.5} fieldName={"dist"} />
                        <ParamField2 size={0.5} fieldName={"cenz"} />
                    </div>
                    <div className="flex flex-row gap-x-5">
                        <ParamField2 size={0.5} fieldName={"anglex"} />
                        <ParamField2 size={0.5} fieldName={"angley"} />
                        <ParamField2 size={0.5} fieldName={"anglez"} />
                    </div>
                    <ParamField2 size={0.5} fieldName={"shift"} />
                </div>
            </div>

            <div className="collapse shadow-xl bg-base-100 collapse-plus">
                <input type="checkbox" />
                <div className="collapse-title text-xl font-medium bg-100 ">
                    Mask
                </div>
                <div className="collapse-content">
                    <div className="">
                        <ParamField2 size={0.5} fieldName={"mask"} />
                        <ParamField2 size={0.5} fieldName={"reversed"} />
                        <ParamField2 size={0.5} fieldName={"bitsizes"} />
                        <ParamField2 size={0.5} fieldName={"thickness"} />
                        <ParamField2 size={0.5} fieldName={"resolution"} />
                        <ParamField2 size={0.5} fieldName={"smoothness"} />
                    </div>
                </div>
            </div>

            <div className="collapse shadow-xl bg-base-100 collapse-plus">
                <input type="checkbox" />
                <div className="collapse-title text-xl font-medium bg-100 ">
                    Motor Path
                </div>
                <div className="collapse-content">
                    <p>hello</p>
                </div>
            </div>

            <div className="collapse shadow-xl bg-base-100 collapse-plus">
                <input type="checkbox" />
                <div className="collapse-title text-xl font-medium bg-100 ">
                    Detector
                </div>
                <div className="collapse-content">
                    <p>hello</p>
                </div>
            </div>

        </div>
    )
}