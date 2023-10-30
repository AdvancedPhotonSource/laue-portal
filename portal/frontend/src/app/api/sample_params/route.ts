const sample_params = {
  "ver": 1.0,
  "file": {
    "path": "/local/laue34/data/Si_MaskZ_step",
    "output": "/local/laue34/outputs/recon_23",
    "pixmask": "../recon_masks/0042_mask_calib3_maskX800_dataset42.npy",
    "range": [
      10,
      701,
      1
    ],
    "threshold": 0,
    "frame": [
      0,
      2048,
      0,
      2048
    ],
    "ext": "h5",
    "stacked": true,
    "h5": {
      "key": "/entry1/data/data"
    }
  },
  "comp": {
    "server": "proc",
    "use_gpu": true,
    "batch_size": 300,
    "workers": 1,
    "scannumber": 1,
    "scanstart": 0
  },
  "geo": {
    "mask": {
      "path": "../masks/code-debruijn-2-8-000.npy",
      "reversed": false,
      "bitsizes": [
        15,
        7.5
      ],
      "thickness": 4.6,
      "resolution": 0.5,
      "smoothness": 0,
      "alpha": 0,
      "widening": 1.7,
      "pad": 150,
      "stretch": 1.0,
      "shift": 0.0,
      "focus": {
        "cenx": -0.0883125,
        "dist": 0.36806641,
        "cenz": -1.67861328,
        "anglex": -0.20322266,
        "angley": -0.28027344,
        "anglez": -1.01757813
      },
      "calibrate": {
        "dist": [
          0.01,
          0.01,
          0.001
        ]
      }
    },
    "scanner": {
      "step": 1,
      "rot": [
        0.0045,
        -0.00684,
        -3.375e-05
      ],
      "axis": [
        1,
        0,
        0
      ]
    },
    "detector": {
      "shape": [
        2048,
        2048
      ],
      "size": [
        409.6,
        409.6
      ],
      "rot": [
        -1.20161887,
        -1.21404493,
        -1.21852276
      ],
      "pos": [
        28.828,
        2.715,
        512.993
      ]
    },
    "source": {
      "offset": 0,
      "grid": [
        -0.3,
        0.3,
        0.001
      ]
    }
  },
  "algo": {
    "iter": 1,
    "pos": {
      "method": "lsqr",
      "regpar": 0,
      "init": "spline"
    },
    "sig": {
      "recon": true,
      "method": "splines",
      "order": 5,
      "scale": 1,
      "init": {
        "maxsize": 64,
        "avgsize": 10,
        "atol": 4
      }
    },
    "ene": {
      "recon": true,
      "exact": true,
      "method": "lsqr",
      "range": [
        10,
        40,
        1
      ]
    }
  }
}

export async function GET(request: Request) {
    return Response.json(sample_params)
}