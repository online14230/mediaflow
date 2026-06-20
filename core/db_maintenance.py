# routes/db_maintenance.py
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from core.db_health import DatabaseHealthChecker
import logging

logger = logging.getLogger(__name__)

db_maintenance_bp = Blueprint('db_maintenance', __name__)

@db_maintenance_bp.route('/admin/db-health')
@login_required
def db_health_page():
    if not current_user.is_admin:
        flash('Admin access required.', 'danger')
        return redirect(url_for('media.dashboard'))
    return render_template('db_health.html')

@db_maintenance_bp.route('/api/db/check', methods=['POST'])
@login_required
def api_db_check():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    checker = DatabaseHealthChecker()
    try:
        report = checker.full_health_check()
        return jsonify(report)
    except Exception as e:
        logger.exception("DB health check failed")
        return jsonify({'error': str(e)}), 500
    finally:
        checker.close()

@db_maintenance_bp.route('/api/db/repair', methods=['POST'])
@login_required
def api_db_repair():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    data = request.json
    delete_missing = data.get('delete_missing_files', False)
    checker = DatabaseHealthChecker()
    try:
        result = checker.full_repair(delete_missing_files=delete_missing)
        return jsonify(result)
    except Exception as e:
        logger.exception("DB repair failed")
        return jsonify({'error': str(e)}), 500
    finally:
        checker.close()