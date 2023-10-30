import React, {useState} from 'react'

export default function ParamField({size, fieldName, defaultValue}) {
  const [value, setValue] = useState(defaultValue)

  let width;

  // Workaround for tailwind. Needs to see whole custom names
  if (size === 'lg') {
    width = 'w-[250px]'
  } else if (size === 'md') {
    width = 'w-[150px]'
  } else if (size === 'sm') {
    width = 'w-[117px]'
  }

  return (
    <div className={width}>
      <label className="label">
        <span className="label-text">{fieldName}</span>
      </label>
      <input type="text" 
             className={`input input-bordered w-full`} 
             defaultValue={defaultValue}
             />
  </div>
  )
}