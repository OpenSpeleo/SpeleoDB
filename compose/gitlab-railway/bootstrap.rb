# Applied after Omnibus migrations on every boot. CI users are provisioned
# explicitly; public signups must stay disabled on this test-only instance.
ApplicationSetting.current.update!(
  signup_enabled: false,
  project_create_limit: 0,
  group_create_limit: 0,
  deletion_adjourned_period: 1
)

# A short-lived administrative token allows first-time API provisioning.
# The operator removes this variable and revokes the token after setup.
bootstrap_token = ENV['GITLAB_BOOTSTRAP_TOKEN']
if bootstrap_token && !bootstrap_token.empty?
  existing = PersonalAccessToken.find_by_token(bootstrap_token)
  unless existing
    token = User.find_by_username!('root').personal_access_tokens.build(
      name: 'railway-initial-provisioning', scopes: ['api'],
      expires_at: 2.days.from_now.to_date
    )
    token.set_token(bootstrap_token)
    token.save!
  end
end

puts 'GitLab test instance settings applied.'
