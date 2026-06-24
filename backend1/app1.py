"""
Flask Backend API for Thesis Simulation Engine
Wraps the scheduler_engine1.py with REST endpoints for running simulations
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
try:
    # Works when run from workspace root as a package
    from backend1.scheduler_engine1 import SimulationEngine, COLLEGES, DOCUMENT_COMPLEXITY, COLLEGE_POPULATION
    from backend1.roc_utils import PRIORITY_ROC_WEIGHTS_BASE, PRIORITY_ROC_WEIGHTS_FULL
except ImportError:
    # Works when run directly from backend1/ as a script
    from scheduler_engine1 import SimulationEngine, COLLEGES, DOCUMENT_COMPLEXITY, COLLEGE_POPULATION
    from roc_utils import PRIORITY_ROC_WEIGHTS_BASE, PRIORITY_ROC_WEIGHTS_FULL


app = Flask(__name__)
CORS(app)  # Enable CORS for frontend access

import sqlite3
import os

def get_db_connection():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, 'custom_requests.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS custom_requests (
            request_id TEXT PRIMARY KEY,
            college TEXT NOT NULL,
            document_type TEXT NOT NULL,
            urgency INTEGER NOT NULL,
            requester_type TEXT NOT NULL,
            submission_time TEXT NOT NULL,
            completeness_of_requirements REAL DEFAULT 1.0,
            payment_status TEXT DEFAULT 'Paid',
            requirements_stage TEXT DEFAULT 'complete',
            requirements_partial_time TEXT,
            requirements_complete_time TEXT,
            payment_time TEXT,
            ready_time TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Auto-initialize database
init_db()


# ============================================================================
# HELPER: Convert responses to JSON-serializable format
# ============================================================================

def to_json_serializable(obj):
    """Convert datetime objects to ISO format strings for JSON"""
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    return str(obj)

app.json.default = to_json_serializable 

def get_staff_info(engine):
    return [{
        "staff_id": s.staff_id,
        "name": s.name,
        "college_affiliation": s.college_affiliation,
        "quota_limit": s.quota_limit,
        "is_available": s.is_available,
        "is_absent": not s.is_available,
        "total_assigned": s.total_assigned,
    } for s in engine.staff_pool]

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "message": "Thesis Simulation Backend Running"})


@app.route('/config', methods=['GET'])
def get_config():
    """Get simulation configuration and constants"""
    return jsonify({
        "colleges": COLLEGES,
        "document_types": list(DOCUMENT_COMPLEXITY.keys()),
        "document_complexity": DOCUMENT_COMPLEXITY,
        "college_population": COLLEGE_POPULATION,
        "allocator_types": ["college_based", "workload_based", "pooled", "quota_free"],
        "scheduler_types": ["FCFS", "WEIGHTED"],
        "scenarios": ["baseline", "staff_absence", "peak_urgency", "workload_imbalance","peak_period"],
        "priority_weights_base": PRIORITY_ROC_WEIGHTS_BASE,
        "priority_weights_full": PRIORITY_ROC_WEIGHTS_FULL
    })


@app.route('/simulate', methods=['POST'])
def run_simulation():
    """
    Run a simulation with custom parameters
    
    Request JSON (all optional):
    {
        "scheduler_type": "FCFS",
        "allocator_type": "college_based",
        "scenario": "baseline",
        "num_staff": 6,
        "quota_limit": 20,
        "total_requests": 200,
        "urgency_base": 5,
        "imbalance_factor": 0,
        "num_absent_staff": 0,
        "random_seed": 12345,
        "work_start": "08:00",
        "work_end": "17:00",
        "priority_weights": {
            "completeness_of_requirements": 0.30,
            "submission_time": 0.22,
            "document_type": 0.18,
            "requester_status": 0.14,
            "college_affiliation": 0.10,
            "payment_status": 0.06
        }
    }
    
    Returns: Simulation metrics and results
    """
    try:
        data = request.get_json() or {}

        scheduler_type = data.get('scheduler_type', 'FCFS')
        allocator_type = data.get('allocator_type', 'college_based')
        scenario = data.get('scenario', 'baseline')
        num_staff = data.get('num_staff', len(COLLEGES))
        quota_limit = data.get('quota_limit', 20)
        total_requests = data.get('total_requests', data.get('num_requests', 200))
        urgency_base = data.get('urgency_base', 5)
        imbalance_factor = data.get('imbalance_factor', 0)
        num_absent_staff = data.get('num_absent_staff', 0)

        absent_staff_ids = data.get("absent_staff_ids", [])
        if isinstance(absent_staff_ids, str):
            absent_staff_ids = [absent_staff_ids]
        absent_staff_ids = [
            str(x).strip()
            for x in absent_staff_ids
            if str(x).strip()
        ]

        random_seed = data.get('random_seed')
        work_start = data.get('work_start', '08:00')
        work_end = data.get('work_end', '17:00')
        priority_weights = data.get('priority_weights')
        urgency = data.get('urgency', False)
        disable_generated_requests = data.get('disable_generated_requests', False)

        if scheduler_type not in ['FCFS', 'WEIGHTED']:
            return jsonify({"error": f"Invalid scheduler_type: {scheduler_type}"}), 400

        if allocator_type not in ['college_based', 'workload_based', 'pooled', 'quota_free']:
            return jsonify({"error": f"Invalid allocator_type: {allocator_type}"}), 400

        if scenario not in ['baseline', 'staff_absence', 'peak_urgency', 'workload_imbalance', 'peak_period']:
            return jsonify({"error": f"Invalid scenario: {scenario}"}), 400

        engine = SimulationEngine(
            scheduler_type=scheduler_type,
            allocator_type=allocator_type,
            staff_config={
                "num_staff": num_staff,
                "quota_limit": quota_limit,
            },
            priority_weights=priority_weights,
            random_seed=random_seed,
            work_start=work_start,
            work_end=work_end,
            urgency=urgency,
        )

        results = engine.run(custom_config={
            "scenario": scenario,
            "total_requests": total_requests,
            "urgency_base": urgency_base,
            "imbalance_factor": imbalance_factor,
            "num_absent_staff": num_absent_staff,
            "absent_staff_ids": absent_staff_ids,
            "disable_generated_requests": disable_generated_requests,
            "sim_start_date": data.get("sim_start_date"),
            "align_custom_dates": data.get("align_custom_dates", False),
            "custom_requests": data.get("custom_requests"),
            "num_staff": num_staff,
            "quota_limit": quota_limit,
            "urgency": urgency,
        })

        staff_info = get_staff_info(engine)

        return jsonify({
            "success": True,
            "parameters": {
                "scheduler_type": scheduler_type,
                "allocator_type": allocator_type,
                "scenario": scenario,
                "num_staff": num_staff,
                "quota_limit": quota_limit,
                "total_requests": total_requests,
                "urgency_base": urgency_base,
                "imbalance_factor": imbalance_factor,
                "num_absent_staff": num_absent_staff,
                "absent_staff_ids": absent_staff_ids,
                "random_seed": results.get("seed_used"),
                "work_start": work_start,
                "work_end": work_end,
            },
            "results": {**results, "staff_info": staff_info},
            "completed_requests": len(engine.completed),
            "staff_load": results["staff_load"],
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/simulate/quick', methods=['POST'])
def run_quick_simulation():
    """
    Run a quick baseline simulation (default parameters)
    
    Request JSON (optional):
    {
        "num_requests": 80  (optional)
    }
    """
    try:
        data = request.get_json() or {}
        random_seed = data.get('random_seed')
        total_requests = data.get('total_requests', data.get('num_requests', 200))
        
        engine = SimulationEngine(
            scheduler_type='FCFS',
            allocator_type='college_based',
            staff_config={"num_staff": len(COLLEGES), "quota_limit": 20},
            random_seed=random_seed,
        )

        results = engine.run(custom_config={
            "scenario": 'baseline',
            "total_requests": total_requests,
        })

        staff_info = get_staff_info(engine)
        
        return jsonify({
            "success": True,
            "results": {**results, "staff_info": staff_info},
            "staff_load": results['staff_load']
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/simulate/compare', methods=['POST'])
def compare_allocators():
    """
    Compare different allocator strategies on same scenario
    
    Request JSON:
    {
        "scenario": "baseline",
        "num_staff": 6,
        "quota_limit": 20
    }
    
    Returns: Results for all 4 allocator types
    """
    try:
        data = request.get_json() or {}
        
        scheduler_type = data.get('scheduler_type', 'FCFS')
        scenario = data.get('scenario', 'baseline')
        num_staff = data.get('num_staff', len(COLLEGES))
        quota_limit = data.get('quota_limit', 20)
        total_requests = data.get('total_requests', 200)
        urgency_base = data.get('urgency_base', 5)
        imbalance_factor = data.get('imbalance_factor', 0)
        num_absent_staff = data.get('num_absent_staff', 0)
        absent_staff_ids = data.get('absent_staff_ids', [])
        if isinstance(absent_staff_ids, str):
            absent_staff_ids = [absent_staff_ids]
        absent_staff_ids = [str(x).strip() for x in absent_staff_ids if str(x).strip()]
        random_seed = data.get('random_seed', 12345)
        work_start = data.get('work_start', '08:00')
        work_end = data.get('work_end', '17:00')
        priority_weights = data.get('priority_weights')
        urgency = data.get('urgency', False)
        disable_generated_requests = data.get('disable_generated_requests', False)
        
        allocators = ['college_based', 'workload_based', 'pooled', 'quota_free']
        results = {}
        
        for allocator in allocators:
            engine = SimulationEngine(
                scheduler_type=scheduler_type,
                allocator_type=allocator,
                staff_config={"num_staff": num_staff, "quota_limit": quota_limit},
                priority_weights=priority_weights,
                random_seed=random_seed,
                work_start=work_start,
                work_end=work_end,
                urgency=urgency,
            )

            sim_results = engine.run(custom_config={
                "scenario": scenario,
                "total_requests": total_requests,
                "urgency_base": urgency_base,
                "imbalance_factor": imbalance_factor,

                # absence config
                "num_absent_staff": num_absent_staff,
                "absent_staff_ids": absent_staff_ids,

                "disable_generated_requests": disable_generated_requests,

                "sim_start_date": data.get("sim_start_date"),
                "align_custom_dates": data.get("align_custom_dates", False),
                "custom_requests": data.get("custom_requests"),
            })
            staff_info = get_staff_info(engine)
            results[allocator] = {
                "metrics": {**sim_results, "staff_info": staff_info},
                "staff_load": sim_results['staff_load']
            }
        
        return jsonify({
            "success": True,
            "scheduler_type": scheduler_type,
            "scenario": scenario,
            "seed_used": random_seed,
            "comparison": results
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/info', methods=['GET'])
def api_info():
    """Get API documentation and available endpoints"""
    return jsonify({
        "version": "1.0",
        "name": "Thesis Simulation Backend",
        "endpoints": {
            "GET /health": "Health check",
            "GET /config": "Get simulation configuration",
            "GET /api/info": "Get API documentation",
            "POST /simulate": "Run simulation with custom parameters",
            "POST /simulate/quick": "Run baseline simulation",
            "POST /simulate/compare": "Compare allocator strategies",
            "GET /api/custom-requests": "List all custom requests in database",
            "POST /api/custom-requests": "Add a custom request to database",
            "DELETE /api/custom-requests": "Clear all custom requests in database",
            "DELETE /api/custom-requests/<request_id>": "Delete a specific custom request by request_id"
        }
    })


@app.route('/api/custom-requests', methods=['GET'])
def get_custom_requests_endpoint():
    """List all custom requests in database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM custom_requests")
        rows = cursor.fetchall()
        conn.close()
        
        results = [dict(row) for row in rows]
        return jsonify(results), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def validate_custom_request(req_data):
    college = req_data.get('college')
    document_type = req_data.get('document_type')
    urgency = req_data.get('urgency')
    requester_type = req_data.get('requester_type')
    submission_time = req_data.get('submission_time')
    
    if not all([college, document_type, urgency, requester_type, submission_time]):
        return False, "Missing required fields (college, document_type, urgency, requester_type, submission_time)"
        
    if college not in COLLEGES:
        return False, f"Invalid college: {college}. Must be one of {COLLEGES}"
        
    if document_type not in DOCUMENT_COMPLEXITY:
        return False, f"Invalid document_type: {document_type}. Must be one of {list(DOCUMENT_COMPLEXITY.keys())}"
        
    try:
        urg_val = int(urgency)
        if not (1 <= urg_val <= 10):
            return False, "Urgency must be an integer between 1 and 10"
    except ValueError:
        return False, "Urgency must be an integer between 1 and 10"
        
    return True, None


@app.route('/api/custom-requests', methods=['POST'])
def add_custom_request_endpoint():
    """Add a custom request or bulk requests to database"""
    try:
        data = request.get_json() or {}
        
        # Check if single object or array
        is_bulk = isinstance(data, list)
        items = data if is_bulk else [data]
        
        # Connect to DB to get current max ID and insert
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get current max CUST number
        cursor.execute("SELECT request_id FROM custom_requests WHERE request_id LIKE 'CUST%'")
        rows = cursor.fetchall()
        max_num = 0
        for row in rows:
            rid = row['request_id']
            try:
                num = int(rid[4:])
                if num > max_num:
                    max_num = num
            except ValueError:
                pass
                
        successes = 0
        failures = 0
        inserted_ids = []
        errors = []
        
        for idx, item in enumerate(items):
            is_valid, err_msg = validate_custom_request(item)
            if not is_valid:
                failures += 1
                errors.append({"index": idx, "error": err_msg})
                continue
                
            # Valid request, let's insert it
            max_num += 1
            request_id = f"CUST{max_num:04d}"
            
            college = item.get('college')
            document_type = item.get('document_type')
            urgency = int(item.get('urgency'))
            requester_type = item.get('requester_type')
            submission_time = item.get('submission_time')
            
            completeness = float(item.get('completeness_of_requirements', 1.0))
            payment_status = item.get('payment_status', 'Paid')
            requirements_stage = item.get('requirements_stage', 'complete')
            
            req_partial = item.get('requirements_partial_time')
            req_complete = item.get('requirements_complete_time')
            payment_time = item.get('payment_time')
            ready_time = item.get('ready_time')
            
            try:
                cursor.execute('''
                    INSERT INTO custom_requests (
                        request_id, college, document_type, urgency, requester_type, submission_time,
                        completeness_of_requirements, payment_status, requirements_stage,
                        requirements_partial_time, requirements_complete_time, payment_time, ready_time
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    request_id, college, document_type, urgency, requester_type, submission_time,
                    completeness, payment_status, requirements_stage,
                    req_partial, req_complete, payment_time, ready_time
                ))
                successes += 1
                inserted_ids.append(request_id)
            except Exception as insert_err:
                failures += 1
                errors.append({"index": idx, "error": str(insert_err)})
                max_num -= 1 # Rollback max_num increment since insert failed
                
        conn.commit()
        conn.close()
        
        response_data = {
            "totals": len(items),
            "successes": successes,
            "failures": failures,
            "request_ids": inserted_ids
        }
        if errors:
            response_data["errors"] = errors
            
        if not is_bulk:
            # Single request format (backward-compatible)
            if successes == 1:
                response_data["success"] = True
                response_data["message"] = "Custom request added successfully"
                response_data["request_id"] = inserted_ids[0]
                return jsonify(response_data), 201
            else:
                return jsonify({"error": errors[0]["error"]}), 400
        else:
            # Bulk request format
            status_code = 201 if successes > 0 else 400
            return jsonify(response_data), status_code
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/custom-requests', methods=['DELETE'])
def clear_custom_requests_endpoint():
    """Clear all custom requests in database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM custom_requests")
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "All custom requests cleared successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/custom-requests/<request_id>', methods=['DELETE'])
def delete_custom_request_endpoint(request_id):
    """Delete a specific custom request by request_id"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM custom_requests WHERE request_id = ?", (request_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": f"Custom request {request_id} deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def server_error(error):
    return jsonify({"error": "Internal server error"}), 500


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print("""
    ===================================================================
    Thesis Simulation Backend API
    ===================================================================
    
    Server running on: http://localhost:5000
    
    Available endpoints:
    * GET  http://localhost:5000/health          - Health check
    * GET  http://localhost:5000/config          - Configuration
    * GET  http://localhost:5000/api/info        - API documentation
    * POST http://localhost:5000/simulate        - Run simulation
    * POST http://localhost:5000/simulate/quick  - Quick baseline
    * POST http://localhost:5000/simulate/compare - Compare allocators
    
    ===================================================================
    """)
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=False  # Disable reloader to avoid double-running simulations
    )