#requires -Version 5.1
[CmdletBinding()]
param()
$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path;$stage=Join-Path $repository 'data\backtests\es_nq_pass_b_staging_3';$archive=Join-Path $repository 'data\backtests\es_nq_pass_b_archive_3';$plan=Get-Content (Join-Path $repository 'data\backtests\es_nq_pass_b_plan_3\plan.json') -Raw|ConvertFrom-Json
$manifests=@(Get-ChildItem $stage -Recurse -Filter '*.json' -ErrorAction SilentlyContinue|Where-Object{$_.Directory.Name-eq'manifests'})
[pscustomobject]@{PlanId=$plan.id;State=$(if(Test-Path $archive){'COMPLETE'}elseif(Test-Path $stage){'IN_PROGRESS'}else{'NOT_STARTED'});CompletedRequests=$manifests.Count;TotalRequests=$plan.estimated.requests;StopRequested=(Test-Path (Join-Path $repository 'data\backtests\es_nq_pass_b.stop'))}|Format-List
