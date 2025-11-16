
use pyo3::prelude::*;
use numpy::{PyArray1, PyArrayMethods};
use ndarray::{Array1, ArrayView1};
use rayon::prelude::*;

/// Calculate moving average using Rust + Rayon for parallel processing
#[pyfunction]
fn moving_average_rust<'py>(
    py: Python<'py>,
    data: PyArray1<f64>,
    window: usize
) -> PyResult<Bound<'py, PyArray1<f64>>> {
    let data_view = data.readonly();
    let slice = data_view.as_slice().unwrap();
    let n = slice.len();
    
    if window > n {
        return Err(pyo3::exceptions::PyValueError::new(
            "Window size must be <= data length"
        ));
    }
    
    let result_len = n - window + 1;
    let mut result = Vec::with_capacity(result_len);
    
    // Parallel calculation using Rayon
    (0..result_len).into_par_iter().for_each(|i| {
        let sum: f64 = slice[i..i + window].iter().sum();
        result[i] = sum / window as f64;
    });
    
    Ok(PyArray1::from_vec_bound(py, result))
}

/// Calculate RSI using optimized Rust implementation
#[pyfunction]
fn rsi_rust<'py>(
    py: Python<'py>,
    data: PyArray1<f64>,
    period: usize
) -> PyResult<Bound<'py, PyArray1<f64>>> {
    let data_view = data.readonly();
    let slice = data_view.as_slice().unwrap();
    let n = slice.len();
    
    if period >= n {
        return Err(pyo3::exceptions::PyValueError::new(
            "Period must be < data length"
        ));
    }
    
    let result_len = n - period;
    let mut result = Vec::with_capacity(result_len);
    
    for i in period..n {
        let mut gains = 0.0;
        let mut losses = 0.0;
        
        for j in (i - period + 1)..=i {
            let change = slice[j] - slice[j - 1];
            if change > 0.0 {
                gains += change;
            } else {
                losses -= change;
            }
        }
        
        let avg_gain = gains / period as f64;
        let avg_loss = losses / period as f64;
        
        if avg_loss == 0.0 {
            result.push(100.0);
        } else {
            let rs = avg_gain / avg_loss;
            result.push(100.0 - (100.0 / (1.0 + rs)));
        }
    }
    
    Ok(PyArray1::from_vec_bound(py, result))
}

/// Fast correlation calculation
#[pyfunction]
fn correlation_rust<'py>(
    py: Python<'py>,
    x: PyArray1<f64>,
    y: PyArray1<f64>
) -> PyResult<f64> {
    let x_view = x.readonly();
    let y_view = y.readonly();
    let x_slice = x_view.as_slice().unwrap();
    let y_slice = y_view.as_slice().unwrap();
    
    if x_slice.len() != y_slice.len() {
        return Err(pyo3::exceptions::PyValueError::new(
            "Arrays must have the same length"
        ));
    }
    
    let n = x_slice.len() as f64;
    let sum_x: f64 = x_slice.iter().sum();
    let sum_y: f64 = y_slice.iter().sum();
    let sum_xy: f64 = x_slice.iter().zip(y_slice.iter()).map(|(a, b)| a * b).sum();
    let sum_x2: f64 = x_slice.iter().map(|x| x * x).sum();
    let sum_y2: f64 = y_slice.iter().map(|y| y * y).sum();
    
    let numerator = n * sum_xy - sum_x * sum_y;
    let denominator = ((n * sum_x2 - sum_x * sum_x) * (n * sum_y2 - sum_y * sum_y)).sqrt();
    
    if denominator == 0.0 {
        Ok(0.0)
    } else {
        Ok(numerator / denominator)
    }
}

#[pymodule]
fn fast_math(_py: Python, m: &Bound<PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(moving_average_rust, m)?)?;
    m.add_function(wrap_pyfunction!(rsi_rust, m)?)?;
    m.add_function(wrap_pyfunction!(correlation_rust, m)?)?;
    Ok(())
}
