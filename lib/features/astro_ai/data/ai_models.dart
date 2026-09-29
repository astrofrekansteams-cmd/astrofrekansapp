import '../../../core/astrology/data/production_models.dart';
import '../../../core/astrology/data/api_contract_dto.dart';

class AIConversation extends ContractRecord {
  AIConversation(super.value) {
    text('id');
    number('message_count');
  }
  String get id => text('id');
  String? get title => optionalText('title');
}

class AIMessage extends ContractRecord {
  AIMessage(super.value) {
    text('id');
    text('content');
    text('role');
  }
  String get content => text('content');
  String get completionStatus =>
      optionalText('completion_status') ?? 'completed';
  List<String> get factorIds => strings('source_factor_ids');
}

class AIReport extends ContractRecord {
  AIReport(super.value) {
    text('id');
    text('report_type');
    text('status');
  }
  String get id => text('id');
  List<ContractRecord> get sections => records('sections');
  List<String> get warnings => strings('warnings');
}

enum ReportJobStatus { queued, running, completed, failed, cancelled, unknown }

class AIReportJob extends ContractRecord {
  AIReportJob(super.value) {
    text('id');
    text('status');
  }
  String get id => text('id');
  String? get reportId => optionalText('report_id');
  ReportJobStatus get status => ContractJson.bySnakeOr(
    ReportJobStatus.values,
    text('status'),
    ReportJobStatus.unknown,
  );
  bool get terminal =>
      status != ReportJobStatus.queued && status != ReportJobStatus.running;
}
