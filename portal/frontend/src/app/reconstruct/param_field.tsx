export default function ParamField({ size, fieldName }) {
  return (
    <div className="input-group">
       <span className="w-20">{fieldName}</span>
      <input type="text join-item" className="input input-bordered" />
    </div>
  )
}